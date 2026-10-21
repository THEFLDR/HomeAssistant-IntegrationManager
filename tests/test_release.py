import json
from copy import deepcopy
from hashlib import sha256

import pytest

from custom_components.integration_manager.models import ManagerError
from scripts.release import promote, publish, registry_api, verify_override
from tests.test_policy import documents


class WorkflowAPI:
    def __init__(self, bundle):
        self.release, self.metadata, self.data = bundle
        self.mutations = []
        self.raw = {
            "id": self.release.release_id,
            "tag_name": self.release.tag,
            "immutable": True,
            "draft": False,
            "prerelease": True,
            "html_url": self.release.html_url,
            "assets": [
                {
                    "name": "integration.zip",
                    "id": self.release.asset_id,
                    "digest": f"sha256:{self.release.sha256}",
                    "size": len(self.data),
                },
                {"name": "integration.json", "id": 999},
            ],
        }
        self.sandbox, self.production = documents(self.release)

    def request(self, method, path, data=None, **kwargs):
        if method == "PATCH":
            self.mutations.append((path, data))
            self.raw["prerelease"] = data["prerelease"]
            return self.raw
        if "IM_STATUS_SANDBOX" in path:
            return {"value": json.dumps(self.sandbox)}
        if "IM_STATUS_PRODUCTION" in path:
            return {"value": json.dumps(self.production)}
        if "/commits/" in path:
            return {"sha": self.release.commit}
        if path.endswith("/assets/999"):
            return json.dumps(self.metadata).encode()
        if "/assets/" in path:
            return self.data
        return deepcopy(self.raw)


def owner_environment():
    return {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY_OWNER": "THEFLDR",
        "GITHUB_ACTOR": "THEFLDR",
        "GITHUB_TRIGGERING_ACTOR": "THEFLDR",
    }


def test_github_side_promotion_preserves_identity_bytes_and_is_idempotent(bundle):
    b = bundle()
    api = WorkflowAPI(b)
    result = promote(
        api,
        api,
        b[0].repository,
        "THEFLDR/HomeAssistant-IntegrationManager",
        b[0].version,
        "demo",
        b[0].release_id,
        b[0].sha256,
    )
    assert result["release"] == b[0].identity()
    assert sha256(api.data).hexdigest() == b[0].sha256
    assert api.mutations == [
        (
            f"/repos/{b[0].repository}/releases/{b[0].release_id}",
            {"prerelease": False, "make_latest": "true"},
        )
    ]
    promote(
        api,
        api,
        b[0].repository,
        "THEFLDR/HomeAssistant-IntegrationManager",
        b[0].version,
        "demo",
        b[0].release_id,
        b[0].sha256,
    )
    assert len(api.mutations) == 1


@pytest.mark.parametrize(
    "field,value",
    [("health", "unknown"), ("state", "pending_restart"), ("health_release_id", 1234)],
)
def test_workflow_rejects_manipulated_or_unverified_status(bundle, field, value):
    b = bundle()
    api = WorkflowAPI(b)
    api.sandbox["integrations"]["demo"][field] = value
    with pytest.raises(ManagerError):
        promote(
            api,
            api,
            b[0].repository,
            "THEFLDR/HomeAssistant-IntegrationManager",
            b[0].version,
            "demo",
            b[0].release_id,
            b[0].sha256,
        )
    assert not api.mutations


@pytest.mark.parametrize("target", ["metadata", "production"])
def test_workflow_rejects_nonobject_documents_before_mutation(bundle, target):
    b = bundle()
    api = WorkflowAPI(b)
    setattr(api, target, [])
    with pytest.raises(ManagerError, match="JSON object|registry document"):
        promote(
            api,
            api,
            b[0].repository,
            "THEFLDR/HomeAssistant-IntegrationManager",
            b[0].version,
            "demo",
            b[0].release_id,
            b[0].sha256,
        )
    assert not api.mutations


@pytest.mark.parametrize("target", ["sandbox", "production"])
@pytest.mark.parametrize("integrations", [[], {"demo": None}, {"demo": []}])
def test_workflow_rejects_malformed_registry_entries_without_changes(bundle, target, integrations):
    b = bundle()
    api = WorkflowAPI(b)
    getattr(api, target)["integrations"] = integrations
    with pytest.raises(ManagerError, match="integrations status"):
        promote(
            api,
            api,
            b[0].repository,
            "THEFLDR/HomeAssistant-IntegrationManager",
            b[0].version,
            "demo",
            b[0].release_id,
            b[0].sha256,
        )
    assert not api.mutations


def test_emergency_override_bypasses_health_only(bundle):
    b = bundle()
    api = WorkflowAPI(b)
    result = promote(
        api,
        api,
        b[0].repository,
        "THEFLDR/HomeAssistant-IntegrationManager",
        b[0].version,
        "demo",
        b[0].release_id,
        b[0].sha256,
        override=True,
        confirmation="THEFLDR authorizes promotion of v0.1.0",
        environment=owner_environment(),
    )
    assert result["override"] and not api.raw["prerelease"]
    api = WorkflowAPI(b)
    api.raw["immutable"] = False
    with pytest.raises(ManagerError, match="immutable"):
        promote(
            api,
            None,
            b[0].repository,
            "THEFLDR/HomeAssistant-IntegrationManager",
            b[0].version,
            "demo",
            b[0].release_id,
            b[0].sha256,
            override=True,
            confirmation="THEFLDR authorizes promotion of v0.1.0",
            environment=owner_environment(),
        )
    assert not api.mutations


@pytest.mark.parametrize(
    "field,value",
    [
        ("GITHUB_ACTOR", "another-user"),
        ("GITHUB_TRIGGERING_ACTOR", "another-user"),
        ("GITHUB_EVENT_NAME", "push"),
        ("GITHUB_REPOSITORY_OWNER", "another-owner"),
    ],
)
def test_override_actor_authorization_before_mutation(bundle, field, value):
    b = bundle()
    api = WorkflowAPI(b)
    environment = owner_environment()
    environment[field] = value
    with pytest.raises(ManagerError, match="THEFLDR"):
        promote(
            api,
            None,
            b[0].repository,
            "THEFLDR/HomeAssistant-IntegrationManager",
            b[0].version,
            "demo",
            b[0].release_id,
            b[0].sha256,
            override=True,
            confirmation="THEFLDR authorizes promotion of v0.1.0",
            environment=environment,
        )
    assert not api.mutations


def test_override_incomplete_confirmation_rejected():
    with pytest.raises(ManagerError):
        verify_override(owner_environment(), "0.1.0", "yes")


def test_override_retains_production_version_gate(bundle):
    b = bundle()
    api = WorkflowAPI(b)
    api.production["integrations"]["demo"].update(
        {
            "state": "active",
            "repository": b[0].repository,
            "running_version": "0.1.0",
            "installed_version": "0.1.0",
        }
    )
    with pytest.raises(ManagerError, match="newer"):
        promote(
            api,
            api,
            b[0].repository,
            "THEFLDR/HomeAssistant-IntegrationManager",
            "0.1.0",
            "demo",
            b[0].release_id,
            b[0].sha256,
            override=True,
            confirmation="THEFLDR authorizes promotion of v0.1.0",
            environment=owner_environment(),
        )
    assert not api.mutations


class PublishAPI(WorkflowAPI):
    def __init__(self, bundle):
        super().__init__(bundle)
        self.checks = [
            {
                "name": "CI / Validation",
                "conclusion": "success",
                "head_sha": self.release.commit,
                "app": {"slug": "github-actions"},
                "details_url": f"https://github.com/{self.release.repository}/actions/runs/123/job/456",
            }
        ]
        self.tags = []
        self.bad_upload = False
        self.full_validation = True

    def request(self, method, path, data=None, **kwargs):
        if path.endswith("/actions/runs/123"):
            return {
                "head_sha": self.release.commit,
                "path": ".github/workflows/ci.yml",
                "conclusion": "success",
            }
        if path.endswith("/actions/runs/123/jobs?per_page=100"):
            if not self.full_validation:
                return {"jobs": [{"name": "CI / Validation", "steps": []}]}
            return {
                "jobs": [
                    {
                        "name": "CI / Validation",
                        "steps": [
                            {"name": name, "conclusion": "success"}
                            for name in (
                                "Quality - Lint, formatting and static analysis",
                                "Tests - Unit and integration tests, "
                                "including Home Assistant compatibility",
                                "Tests - Package integrity and repository contracts",
                                "Security - Code and dependency audit",
                            )
                        ],
                    }
                ]
            }
        if path.endswith("check-runs?per_page=100"):
            return {"check_runs": self.checks}
        if "/git/matching-refs/" in path:
            return self.tags
        if path == f"/repos/{self.release.repository}":
            return {"default_branch": "main"}
        if method == "POST":
            self.mutations.append((path, data))
            if "/assets?" in path:
                return {
                    "digest": "sha256:"
                    + ("0" * 64 if self.bad_upload else sha256(data).hexdigest())
                }
            self.raw["draft"] = True
            return {"id": self.release.release_id}
        if method == "PATCH":
            self.mutations.append((path, data))
            self.raw.update({key: value for key, value in data.items() if key != "make_latest"})
            return self.raw
        return super().request(method, path, data, **kwargs)


def test_publish_once_as_draft_then_verified_immutable_rc(bundle, tmp_path, monkeypatch):
    b = bundle()
    api = PublishAPI(b)
    api.checks[0]["details_url"] = "https://github.com/THEFLDR/DeMo/actions/runs/123/job/456"
    monkeypatch.setenv("GITHUB_SHA", b[0].commit)
    source = tmp_path / "sources/demo-0.1.0"
    result = publish(api, b[0].repository, source, "0.1.0", b[0].commit)
    assert result["release"] == b[0].identity()
    assert api.mutations[0][1]["draft"] is True
    assert len(api.mutations) == 4
    assert api.mutations[-1][1] == {"draft": False, "prerelease": True, "make_latest": "false"}


@pytest.mark.parametrize("invalid", ["missing-check", "wrong-sha", "existing-tag", "docs-only"])
def test_publish_gate_rejects_without_mutation(bundle, tmp_path, monkeypatch, invalid):
    b = bundle()
    api = PublishAPI(b)
    monkeypatch.setenv("GITHUB_SHA", b[0].commit)
    if invalid == "missing-check":
        api.checks = []
    elif invalid == "wrong-sha":
        api.checks[0]["head_sha"] = "b" * 40
    elif invalid == "existing-tag":
        api.tags = [{"ref": "refs/tags/v0.1.0"}]
    else:
        api.full_validation = False
    with pytest.raises(ManagerError):
        publish(api, b[0].repository, tmp_path / "sources/demo-0.1.0", "0.1.0", b[0].commit)
    assert not api.mutations


def test_publish_upload_failure_does_not_publish_draft(bundle, tmp_path, monkeypatch):
    b = bundle()
    api = PublishAPI(b)
    api.bad_upload = True
    monkeypatch.setenv("GITHUB_SHA", b[0].commit)
    with pytest.raises(ManagerError, match="draft left"):
        publish(api, b[0].repository, tmp_path / "sources/demo-0.1.0", "0.1.0", b[0].commit)
    assert api.raw["draft"] is True and len(api.mutations) == 2


def test_registry_jwt_scope_is_read_only(pem):
    from unittest.mock import patch

    environment = {
        "IM_CLIENT_ID": "client-example",
        "IM_INSTALLATION_ID": "456",
        "IM_APP_PRIVATE_KEY": pem,
    }
    with patch("scripts.release.API") as api:
        api.return_value.request.return_value = {
            "token": "scoped-placeholder",
            "permissions": {"actions_variables": "read"},
        }
        registry_api(environment, "THEFLDR/HomeAssistant-IntegrationManager")
        payload = api.return_value.request.call_args.args[2]
        assert payload == {
            "repositories": ["homeassistant-integrationmanager"],
            "permissions": {"contents": "read", "actions_variables": "read"},
        }


def test_workflow_promotion_accepts_repository_case_without_weakening_identity(bundle):
    b = bundle()
    api = WorkflowAPI(b)
    api.sandbox["integrations"]["demo"]["release"]["repository"] = b[0].repository.upper()
    api.production["integrations"]["demo"]["repository"] = b[0].repository.swapcase()
    result = promote(
        api,
        api,
        b[0].repository.upper(),
        "ThEfLdR/HomeAssistant-IntegrationManager",
        b[0].version,
        "demo",
        b[0].release_id,
        b[0].sha256,
    )
    assert result["release"] == b[0].identity()
    assert len(api.mutations) == 1
