import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_ci_is_one_stable_required_check_and_docs_path_is_present():
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    assert ci["name"] == "CI - Validation"
    assert set(ci[True]) == {"pull_request", "workflow_dispatch"}  # YAML 1.1 treats 'on' as True.
    assert len(ci["jobs"]) == 1
    job = next(iter(ci["jobs"].values()))
    assert job["name"] == "CI / Validation"
    assert any("--light" in step.get("run", "") for step in job["steps"])
    assert "edited" in ci[True]["pull_request"]["types"]
    python_step = next(
        i
        for i, step in enumerate(job["steps"])
        if step.get("uses", "").startswith("actions/setup-python@")
    )
    light_step = next(i for i, step in enumerate(job["steps"]) if "--light" in step.get("run", ""))
    assert python_step < light_step and "if" not in job["steps"][python_step]
    assert len([step for step in job["steps"] if "pip install" in step.get("run", "")]) == 1
    assert ci["permissions"] == {"contents": "read"}
    assert ci["concurrency"]["cancel-in-progress"] is True


def test_release_workflows_are_distinct_and_override_is_manual_only():
    names = {
        "release.yml": "Release - Publish",
        "promote.yml": "Release - Promote",
        "override.yml": "Release - Override",
    }
    for file, name in names.items():
        workflow = yaml.safe_load((ROOT / ".github/workflows" / file).read_text())
        assert workflow["name"] == name
        assert set(workflow[True]) == {"workflow_dispatch"}
        for job in workflow["jobs"].values():
            assert "default_branch" in job["if"]
            for step in job["steps"]:
                if action := step.get("uses"):
                    assert re.fullmatch(r"actions/(checkout|setup-python)@[0-9a-f]{40}", action)
        if file == "override.yml":
            steps = next(iter(workflow["jobs"].values()))["steps"]
            authorization = next(
                i for i, s in enumerate(steps) if "authorize-override" in s.get("run", "")
            )
            mutation = next(
                i for i, s in enumerate(steps) if s.get("run", "").endswith("release.py override")
            )
            assert authorization < mutation


def test_release_dependencies_are_in_full_security_audit():
    pattern = r"^([a-z0-9_.-]+)==([^\s\\]+)"
    development = dict(re.findall(pattern, (ROOT / "requirements-dev.lock").read_text(), re.M))
    release = dict(re.findall(pattern, (ROOT / "requirements-release.lock").read_text(), re.M))
    assert release and all(development.get(name) == pin for name, pin in release.items())
