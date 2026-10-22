import re
from pathlib import Path

import pytest
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


def test_release_orchestrates_ci_with_minimum_dispatch_permission():
    release = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    assert release["permissions"] == {"contents": "write", "checks": "read", "actions": "write"}
    steps = release["jobs"]["publish"]["steps"]
    validation = next(
        i for i, step in enumerate(steps) if step.get("run", "").endswith("ensure-ci")
    )
    publish = next(i for i, step in enumerate(steps) if step.get("run", "").endswith("publish"))
    assert validation < publish


@pytest.mark.parametrize("matches", [False, True])
def test_release_dispatch_checkout_must_match_expected_sha_before_full_ci(tmp_path, matches):
    import os
    import shutil
    import subprocess

    # Run the real detection step against a local git commit, before dependency installation.
    git = shutil.which("git")
    bash = shutil.which("bash")
    assert git and bash
    subprocess.run([git, "init", "-q", str(tmp_path)], check=True)  # noqa: S603 - local fixture paths
    subprocess.run(  # noqa: S603 - resolved git executable and fixed fixture arguments
        [
            git,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "fixture",
        ],
        cwd=tmp_path,
        check=True,
    )
    sha = subprocess.check_output(  # noqa: S603 - resolved git executable, fixed arguments
        [git, "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    step = next(s for s in ci["jobs"]["validation"]["steps"] if s.get("id") == "changes")
    output = tmp_path / "output"
    # Exercise the trusted repository workflow script, with no external code or inputs.
    result = subprocess.run(  # noqa: S603
        [bash, "-e", "-c", step["run"]],
        cwd=tmp_path,
        capture_output=True,
        env={
            **os.environ,
            "EVENT_NAME": "workflow_dispatch",
            "EXPECTED_SHA": sha if matches else "b" * 40,
            "GITHUB_OUTPUT": str(output),
        },
        text=True,
    )
    assert result.returncode == (0 if matches else 1)
    assert output.read_text() == "full=true\n" if matches else not output.exists()
