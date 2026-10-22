import importlib.util
import json
import subprocess
import sys

import pytest
import yaml

from custom_components.integration_manager.models import ManagerError
from scripts.prepare_managed_repository import prepare
from tests.test_release import PublishAPI, WorkflowAPI

COMMANDS = {
    "quality": "ruff check custom_components tests && ruff format --check custom_components tests",
    "tests": "pytest tests/unit tests/homeassistant",
    "package": "python -m compileall -q custom_components/demo",
    "security": (
        "bandit -r custom_components && pip-audit -r requirements-dev.lock --require-hashes"
    ),
}


def target_repository(tmp_path, bundle):
    b = bundle()
    target = tmp_path / "sources/demo-0.1.0"
    (target / "custom_components").mkdir()
    # Keep the package source untouched for fixture comparisons.
    destination = target / "custom_components/demo"
    destination.mkdir()
    for name in ("manifest.json", "__init__.py"):
        (destination / name).write_bytes((target / name).read_bytes())
    (target / "requirements-dev.lock").write_text("# This project's separately reviewed lock\n")
    return target, b


def test_complete_foreign_bundle_packages_publishes_and_promotes(tmp_path, bundle, monkeypatch):
    target, b = target_repository(tmp_path, bundle)
    written = prepare(target, "demo", COMMANDS)
    assert len(written) == 12
    assert not (target / "custom_components/integration_manager").exists()
    ci = yaml.safe_load((target / ".github/workflows/ci.yml").read_text())
    assert "expected_sha" in ci["on"]["workflow_dispatch"]["inputs"]
    assert len(ci["jobs"]) == 1
    steps = ci["jobs"]["validation"]["steps"]
    assert any(s.get("run") == COMMANDS["tests"] for s in steps)
    for name in ("release.yml", "promote.yml", "override.yml"):
        workflow = yaml.safe_load((target / ".github/workflows" / name).read_text())
        assert set(workflow[True]) == {"workflow_dispatch"}
    # A standalone command must work without Home Assistant or this repository on PYTHONPATH.
    result = subprocess.run(
        [sys.executable, "scripts/release.py", "package", "--source", "custom_components/demo"],
        cwd=target,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Validated demo 0.1.0" in result.stdout
    monkeypatch.syspath_prepend(str(target))
    for name in ("artifacts", "auth", "const", "models", "policy", "__init__"):
        monkeypatch.delitem(sys.modules, f"scripts.im_release.{name}", raising=False)
    monkeypatch.delitem(sys.modules, "scripts.im_release", raising=False)
    spec = importlib.util.spec_from_file_location("exported_release", target / "scripts/release.py")
    exported = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exported)
    api = PublishAPI(b)
    monkeypatch.setenv("GITHUB_SHA", b[0].commit)
    assert (
        exported.publish(
            api, b[0].repository, target / "custom_components/demo", "0.1.0", b[0].commit
        )["result"]
        == "rc"
    )
    api = WorkflowAPI(b)
    assert (
        exported.promote(
            api,
            api,
            b[0].repository,
            "thefldr/homeassistant-integrationmanager",
            "0.1.0",
            "demo",
            b[0].release_id,
            b[0].sha256,
        )["result"]
        == "stable"
    )
    assert len(api.mutations) == 1
    assert exported.ManagerError.__module__ == "scripts.im_release.models"


@pytest.mark.parametrize("missing", ["commands", "lock", "domain", "existing-workflow"])
def test_foreign_setup_reports_missing_requirements_without_partial_writes(
    tmp_path, bundle, missing
):
    target, _ = target_repository(tmp_path, bundle)
    commands = COMMANDS.copy()
    if missing == "commands":
        commands.pop("security")
    elif missing == "lock":
        (target / "requirements-dev.lock").unlink()
    elif missing == "domain":
        path = target / "custom_components/demo/manifest.json"
        path.write_text(json.dumps({"domain": "other"}))
    else:
        path = target / ".github/workflows/promote.yml"
        path.parent.mkdir(parents=True)
        path.write_text("existing workflow\n")
    with pytest.raises(ManagerError):
        prepare(target, "demo", commands)
    assert not (target / "scripts/release.py").exists()
