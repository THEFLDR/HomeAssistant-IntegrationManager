from copy import deepcopy

import pytest

from custom_components.integration_manager.models import ManagerError
from scripts.release import ensure_ci
from tests.test_release import PublishAPI


class ValidationAPI(PublishAPI):
    def __init__(self, bundle):
        super().__init__(bundle)
        self.full = deepcopy(self.checks)
        self.dispatches = []
        self.runs = []
        self.next_checks = self.full
        self.advance = False

    def request(self, method, path, data=None, **kwargs):
        if path.endswith("/ci.yml/dispatches"):
            self.dispatches.append(data)
            self.checks = self.next_checks
            return None
        if "/ci.yml/runs?" in path:
            return {"workflow_runs": self.runs}
        if path.endswith("/commits/main") and self.advance:
            return {"sha": "b" * 40}
        return super().request(method, path, data, **kwargs)


def test_exact_full_release_validation_is_reused_without_dispatch(bundle):
    api = ValidationAPI(bundle())
    ensure_ci(api, api.release.repository, api.release.commit)
    assert not api.dispatches


@pytest.mark.parametrize("reason", ["squash-sha", "docs-only"])
def test_release_automatically_validates_exact_commit_once(bundle, monkeypatch, reason):
    api = ValidationAPI(bundle())
    if reason == "squash-sha":
        api.checks[0]["head_sha"] = "b" * 40
    else:
        api.full_validation = False

    def finish(_):
        api.full_validation = True

    monkeypatch.setattr("scripts.release.time.sleep", finish)
    ensure_ci(api, api.release.repository, api.release.commit)
    assert api.dispatches == [{"ref": "main", "inputs": {"expected_sha": api.release.commit}}]


def test_existing_pending_ci_is_awaited_without_duplicate_dispatch(bundle, monkeypatch):
    api = ValidationAPI(bundle())
    api.checks = []
    api.runs = [{"id": 5, "head_sha": api.release.commit, "status": "in_progress"}]

    def finish(_):
        api.checks = api.full

    monkeypatch.setattr("scripts.release.time.sleep", finish)
    ensure_ci(api, api.release.repository, api.release.commit)
    assert not api.dispatches


@pytest.mark.parametrize("failure", ["moved", "timeout", "failed"])
def test_no_release_changes_without_exact_success(bundle, monkeypatch, failure):
    api = ValidationAPI(bundle())
    api.checks = []
    api.next_checks = []
    api.advance = failure == "moved"

    def finish(_):
        api.runs = [
            {
                "id": 6,
                "head_sha": api.release.commit,
                "status": "completed",
                "event": "workflow_dispatch",
                "conclusion": "failure",
            }
        ]

    monkeypatch.setattr("scripts.release.time.sleep", finish)
    with pytest.raises(ManagerError):
        ensure_ci(
            api,
            api.release.repository,
            api.release.commit,
            timeout=0 if failure == "timeout" else 100,
        )
    assert not api.mutations


def test_retry_waits_for_new_dispatch_without_mistaking_old_failed_run(bundle, monkeypatch):
    api = ValidationAPI(bundle())
    api.checks = api.next_checks = []
    api.runs = [
        {
            "id": 5,
            "head_sha": api.release.commit,
            "status": "completed",
            "event": "workflow_dispatch",
            "conclusion": "failure",
        }
    ]
    ticks = []

    def finish(_):
        ticks.append(True)
        if len(ticks) == 2:
            api.checks = api.full

    monkeypatch.setattr("scripts.release.time.sleep", finish)
    ensure_ci(api, api.release.repository, api.release.commit)
    assert len(api.dispatches) == 1 and len(ticks) == 2
