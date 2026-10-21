#!/usr/bin/env python3
"""Release publication and promotion; run only from trusted default-branch workflows."""

import argparse
import json
import os
import re
import sys
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.integration_manager.artifacts import (  # noqa: E402
    build_package,
    inspect_package,
)
from custom_components.integration_manager.const import MAX_PACKAGE_BYTES  # noqa: E402
from custom_components.integration_manager.models import (  # noqa: E402
    ManagerError,
    Release,
    domain_name,
    repository,
    version,
)
from custom_components.integration_manager.policy import (  # noqa: E402
    validate_production,
    validate_promotion,
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class API:
    def __init__(self, token: str) -> None:
        if not token:
            raise ManagerError("Missing workflow token")
        self.token = token

    def request(self, method: str, path: str, data=None, *, binary=False, upload=False):
        host = "https://uploads.github.com" if upload else "https://api.github.com"
        if not path.startswith("/") or path.startswith("//"):
            raise ManagerError("Invalid GitHub API path")
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2026-03-10",
            "Accept": "application/octet-stream" if binary else "application/vnd.github+json",
        }
        if isinstance(data, bytes):
            headers["Content-Type"] = "application/octet-stream"
        elif data is not None:
            data = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        # Both possible hosts are fixed HTTPS origins; paths cannot replace the host.
        req = Request(host + path, data=data, method=method, headers=headers)  # noqa: S310
        try:
            # Fixed HTTPS GitHub origin above, with redirects disabled.
            with build_opener(NoRedirect).open(req, timeout=90) as response:  # noqa: S310
                raw = response.read(MAX_PACKAGE_BYTES + 1)
                if len(raw) > MAX_PACKAGE_BYTES:
                    raise ManagerError("GitHub response exceeds size limit")
                return raw if binary else json.loads(raw) if raw else None
        except HTTPError as err:
            if binary and err.code in (301, 302, 307):
                url = err.headers.get("Location", "")
                parsed = urlparse(url)
                if (
                    parsed.scheme != "https"
                    or parsed.hostname != "release-assets.githubusercontent.com"
                    or parsed.username
                ):
                    raise ManagerError("Unexpected asset redirect") from None
                # Do not forward authorization to signed download URLs.
                with build_opener(NoRedirect).open(url, timeout=90) as response:
                    raw = response.read(MAX_PACKAGE_BYTES + 1)
                    if len(raw) > MAX_PACKAGE_BYTES:
                        raise ManagerError("Asset exceeds size limit") from None
                    return raw
            raise ManagerError(f"GitHub {method} {path.split('?')[0]}: HTTP {err.code}") from None


def read_status(api: API, registry: str, environment: str) -> dict:
    result = api.request(
        "GET", f"/repos/{registry}/actions/variables/IM_STATUS_{environment.upper()}"
    )
    try:
        document = json.loads(result["value"])
        if not isinstance(document, dict):
            raise ValueError("Registry document must be an object")
        return document
    except (KeyError, ValueError, TypeError) as err:
        raise ManagerError(f"Invalid {environment} registry document") from err


def registry_api(environment: dict, registry: str) -> API:
    from custom_components.integration_manager.auth import assertion

    installation = environment.get("IM_INSTALLATION_ID", "")
    identity = environment.get("IM_CLIENT_ID") or environment.get("IM_APP_ID", "")
    if not installation.isdigit() or not identity or not environment.get("IM_APP_PRIVATE_KEY"):
        raise ManagerError(
            "Owner must configure IM_CLIENT_ID (or IM_APP_ID), IM_INSTALLATION_ID "
            "and IM_APP_PRIVATE_KEY"
        )
    result = API(assertion(identity, environment["IM_APP_PRIVATE_KEY"])).request(
        "POST",
        f"/app/installations/{installation}/access_tokens",
        {
            "repositories": [repository(registry).split("/")[1]],
            "permissions": {"contents": "read", "actions_variables": "read"},
        },
    )
    if result.get("permissions", {}).get("actions_variables") != "read":
        raise ManagerError("Registry token did not receive Variables read permission")
    return API(result["token"])


def load_release(api: API, repo: str, raw: dict) -> tuple[Release, dict, bytes]:
    ver = raw["tag_name"].removeprefix("v")
    version(ver)
    if raw.get("draft") or not raw.get("immutable") or raw["tag_name"] != f"v{ver}":
        raise ManagerError("Release must be published and immutable with a canonical SemVer tag")
    assets = {a["name"]: a for a in raw["assets"]}
    try:
        asset = assets["integration.zip"]
        metadata = json.loads(
            api.request(
                "GET",
                f"/repos/{repo}/releases/assets/{assets['integration.json']['id']}",
                binary=True,
            )
        )
        data = api.request("GET", f"/repos/{repo}/releases/assets/{asset['id']}", binary=True)
    except (KeyError, ValueError) as err:
        raise ManagerError("Release lacks valid package assets") from err
    if not isinstance(metadata, dict):
        raise ManagerError("Release metadata must be a JSON object")
    digest = sha256(data).hexdigest()
    if (
        asset.get("digest") != f"sha256:{digest}"
        or metadata.get("sha256") != digest
        or metadata.get("version") != ver
        or metadata.get("size") != len(data)
        or asset.get("size") != len(data)
        or metadata.get("schema_version") != 1
    ):
        raise ManagerError("Artifact identity, metadata, size or GitHub digest mismatch")
    inspect_package(data, metadata)
    commit = api.request("GET", f"/repos/{repo}/commits/{raw['tag_name']}")["sha"]
    release = Release(
        repo,
        raw["id"],
        raw["tag_name"],
        ver,
        commit,
        asset["id"],
        digest,
        raw["prerelease"],
        raw["immutable"],
        raw["html_url"],
    )
    return release, metadata, data


def verify_override(environment: dict, ver: str, confirmation: str) -> None:
    """GitHub does not expose UI/CLI/API provenance for workflow_dispatch."""
    version(ver)
    if (
        environment.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or environment.get("GITHUB_REPOSITORY_OWNER", "").lower() != "thefldr"
        or environment.get("GITHUB_ACTOR", "").lower() != "thefldr"
        or environment.get("GITHUB_TRIGGERING_ACTOR", "").lower() != "thefldr"
        or confirmation != f"THEFLDR authorizes promotion of v{ver}"
    ):
        raise ManagerError(
            "Emergency override requires THEFLDR as actor and triggering actor, "
            "plus exact confirmation"
        )


def promote(
    api: API,
    status_api: API | None,
    repo: str,
    registry: str,
    ver: str,
    domain: str,
    release_id: int,
    digest: str,
    *,
    override=False,
    confirmation="",
    environment=None,
) -> dict:
    repository(repo)
    repository(registry)
    domain_name(domain)
    version(ver)
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ManagerError("An explicit artifact SHA-256 is required")
    if override:
        verify_override(environment or dict(os.environ), ver, confirmation)
    raw = api.request("GET", f"/repos/{repo}/releases/{int(release_id)}")
    release, metadata, _ = load_release(api, repo, raw)
    if release.tag != f"v{ver}" or release.sha256 != digest or metadata["domain"] != domain:
        raise ManagerError("Requested version, domain or artifact does not match release")
    if status_api is None:
        raise ManagerError("Status registry authentication is required for version safety")
    production = read_status(status_api, registry, "production")
    if override:
        validate_production(release, production, domain)
    else:
        validate_promotion(
            release,
            read_status(status_api, registry, "sandbox"),
            production,
            domain,
        )
    if release.prerelease:
        # This is the sole release mutation during promotion. Never edit tags/assets.
        api.request(
            "PATCH",
            f"/repos/{repo}/releases/{release.release_id}",
            {"prerelease": False, "make_latest": "true"},
        )
    final_raw = api.request("GET", f"/repos/{repo}/releases/{release.release_id}")
    final, _, final_data = load_release(api, repo, final_raw)
    if (
        final.prerelease
        or final.identity() != release.identity()
        or sha256(final_data).hexdigest() != digest
    ):
        raise ManagerError(
            "Post-promotion channel, immutability or exact identity verification failed"
        )
    return {"result": "stable", "override": override, "release": final.identity()}


def validated_commit(api: API, repo: str, commit: str, checks: list[dict]) -> bool:
    """A docs-only green check must not stand in for full release validation."""
    required_steps = {
        "Quality - Lint, formatting and static analysis",
        "Tests - Unit and integration tests, including Home Assistant compatibility",
        "Tests - Package integrity and repository contracts",
        "Security - Code and dependency audit",
    }
    for check in checks:
        if (
            check.get("name") != "CI / Validation"
            or check.get("conclusion") != "success"
            or check.get("head_sha") != commit
            or check.get("app", {}).get("slug") != "github-actions"
        ):
            continue
        match = re.fullmatch(
            rf"https://github\.com/{re.escape(repo)}/actions/runs/(\d+)/job/\d+",
            check.get("details_url", ""),
        )
        if not match:
            continue
        run_id = match[1]
        run = api.request("GET", f"/repos/{repo}/actions/runs/{run_id}")
        if (
            run.get("head_sha") != commit
            or run.get("path", "").split("@")[0] != ".github/workflows/ci.yml"
            or run.get("conclusion") != "success"
        ):
            continue
        jobs = api.request("GET", f"/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")
        for job in jobs["jobs"]:
            completed = {
                s["name"] for s in job.get("steps", []) if s.get("conclusion") == "success"
            }
            if job["name"] == "CI / Validation" and required_steps <= completed:
                return True
    return False


def publish(api: API, repo: str, source: Path, ver: str, commit: str) -> dict:
    repository(repo)
    version(ver)
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ManagerError("An exact reviewed commit SHA is required")
    info = api.request("GET", f"/repos/{repo}")
    latest = api.request("GET", f"/repos/{repo}/commits/{info['default_branch']}")
    if latest["sha"] != commit or os.environ.get("GITHUB_SHA") != commit:
        raise ManagerError("Publish only the exact current default-branch commit")
    runs = api.request("GET", f"/repos/{repo}/commits/{commit}/check-runs?per_page=100")
    if not validated_commit(api, repo, commit, runs["check_runs"]):
        raise ManagerError(
            "Exact release commit lacks successful CI / Validation; dispatch CI for that SHA"
        )
    manifest = json.loads((source / "manifest.json").read_text())
    if manifest["version"] != ver:
        raise ManagerError("Requested release differs from integration manifest")
    data, metadata = build_package(source, manifest["domain"])
    tag = f"v{ver}"
    # Never reuse a tag, draft or published release. GitHub enforces immutable tag reuse too.
    tags = api.request("GET", f"/repos/{repo}/git/matching-refs/tags/{tag}")
    if any(ref["ref"] == f"refs/tags/{tag}" for ref in tags):
        raise ManagerError("Release tag already exists; use a new version")
    draft = api.request(
        "POST",
        f"/repos/{repo}/releases",
        {
            "tag_name": tag,
            "target_commitish": commit,
            "name": tag,
            "draft": True,
            "prerelease": True,
            "generate_release_notes": True,
        },
    )
    rid = draft["id"]
    for name, content in (
        ("integration.zip", data),
        ("integration.json", json.dumps(metadata, sort_keys=True).encode()),
    ):
        uploaded = api.request(
            "POST", f"/repos/{repo}/releases/{rid}/assets?name={quote(name)}", content, upload=True
        )
        if uploaded.get("digest") != f"sha256:{sha256(content).hexdigest()}":
            raise ManagerError("Uploaded asset digest mismatch; draft left for owner inspection")
    api.request(
        "PATCH",
        f"/repos/{repo}/releases/{rid}",
        {"draft": False, "prerelease": True, "make_latest": "false"},
    )
    raw = api.request("GET", f"/repos/{repo}/releases/{rid}")
    release, _, _ = load_release(api, repo, raw)
    if not release.prerelease or release.commit != commit or release.sha256 != metadata["sha256"]:
        raise ManagerError(
            "Publication verification failed; inspect release before any installation"
        )
    return {"result": "rc", "release": release.identity()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "operation", choices=["package", "publish", "promote", "override", "authorize-override"]
    )
    parser.add_argument("--source", default="custom_components/integration_manager")
    parser.add_argument("--output", default="dist")
    args = parser.parse_args()
    env = dict(os.environ)
    ver = env.get("IM_VERSION", "")
    if args.operation == "authorize-override":
        verify_override(env, ver, env.get("IM_CONFIRMATION", ""))
        print("Owner authorization verified; no release changes performed")
        return
    if args.operation == "package":
        source = Path(args.source)
        manifest = json.loads((source / "manifest.json").read_text())
        data, metadata = build_package(source, manifest["domain"])
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        (output / "integration.zip").write_bytes(data)
        (output / "integration.json").write_text(json.dumps(metadata, indent=2) + "\n")
        print(f"Validated {metadata['domain']} {metadata['version']}: {metadata['sha256']}")
        return
    repo = repository(env["GITHUB_REPOSITORY"])
    api = API(env["GH_TOKEN"])
    info = api.request("GET", f"/repos/{repo}")
    if env.get("GITHUB_REF") != f"refs/heads/{info['default_branch']}":
        raise ManagerError("Privileged releases execute on the default branch only")
    if args.operation == "publish":
        result = publish(api, repo, Path(args.source), ver, env["GITHUB_SHA"])
    else:
        if args.operation == "override":
            verify_override(env, ver, env.get("IM_CONFIRMATION", ""))
        registry = repository(env.get("IM_REGISTRY_REPOSITORY", ""))
        if args.operation == "promote" and env.get("IM_REQUEST_REGISTRY") != registry:
            raise ManagerError("Requested registry differs from owner-configured registry")
        status_api = registry_api(env, registry)
        try:
            result = promote(
                api,
                status_api,
                repo,
                registry,
                ver,
                env["IM_DOMAIN"],
                int(env["IM_RELEASE_ID"]),
                env["IM_SHA256"],
                override=args.operation == "override",
                confirmation=env.get("IM_CONFIRMATION", ""),
                environment=env,
            )
        finally:
            status_api.request("DELETE", "/installation/token")
    audit = {
        **result,
        "actor": env.get("GITHUB_ACTOR"),
        "triggering_actor": env.get("GITHUB_TRIGGERING_ACTOR"),
        "run_id": env.get("GITHUB_RUN_ID"),
    }
    text = json.dumps(audit, indent=2)
    print(text)
    if summary := env.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a") as stream:
            stream.write(f"\n```json\n{text}\n```\n")


if __name__ == "__main__":
    try:
        main()
    except (ManagerError, KeyError, ValueError, OSError) as err:
        # Do not print exception chains that may contain signed URLs or credentials.
        reason = str(err) if isinstance(err, ManagerError) else type(err).__name__
        print(f"Release operation rejected: {reason}", file=sys.stderr)
        sys.exit(1)
