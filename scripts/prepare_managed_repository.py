#!/usr/bin/env python3
"""Prepare a reviewed, local workflow installation for another managed repository."""

import argparse
import json
from pathlib import Path

import yaml

from custom_components.integration_manager.models import ManagerError, domain_name

ROOT = Path(__file__).resolve().parents[1]


def prepare(target: Path, domain: str, commands: dict) -> list[Path]:
    """No GitHub writes or settings changes; refuse to overwrite existing workflow tooling."""
    domain_name(domain)
    manifest = json.loads((target / f"custom_components/{domain}/manifest.json").read_text())
    if manifest.get("domain") != domain:
        raise ManagerError("Target manifest domain does not match the requested domain")
    if not (target / "requirements-dev.lock").is_file():
        raise ManagerError("Provide this integration's own hashed requirements-dev.lock first")
    categories = ("quality", "tests", "package", "security")
    if set(commands) != set(categories) or any(
        not isinstance(commands[c], str) or not commands[c].strip() for c in categories
    ):
        raise ManagerError(
            "Provide quality, tests (including HA compatibility), package and security commands"
        )
    files = {}
    for name in ("release.yml", "promote.yml", "override.yml"):
        content = (ROOT / ".github/workflows" / name).read_text()
        if name == "release.yml":
            for operation in ("ensure-ci", "publish"):
                content = content.replace(
                    f"scripts/release.py {operation}",
                    f"scripts/release.py {operation} --source custom_components/{domain}",
                )
        files[f".github/workflows/{name}"] = content
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    ci["on"] = ci.pop(True)  # PyYAML's YAML 1.1 'on' boolean; emit a quoted workflow key.
    steps = ci["jobs"]["validation"]["steps"]
    for step in steps:
        name = step.get("name", "")
        if name == "Quality - Documentation and repository contracts":
            step["run"] = f"python -m compileall -q custom_components/{domain}"
        elif name == "Quality - Lint, formatting and static analysis":
            step["run"] = commands["quality"]
        elif name.startswith("Tests - Unit and integration tests"):
            step["run"] = commands["tests"]
        elif name == "Tests - Package integrity and repository contracts":
            step["run"] = (
                commands["package"]
                + f"\npython scripts/release.py package --source custom_components/{domain}"
            )
        elif name == "Security - Code and dependency audit":
            step["run"] = commands["security"] + (
                "\npython -m pip_audit -r requirements-release.lock "
                "--require-hashes --no-deps --disable-pip"
            )
    files[".github/workflows/ci.yml"] = yaml.safe_dump(ci, sort_keys=False, width=120)
    # Vendor only the small shared release implementation, never a second HA integration.
    for name in ("artifacts.py", "auth.py", "const.py", "models.py", "policy.py"):
        files[f"scripts/im_release/{name}"] = (
            ROOT / "custom_components/integration_manager" / name
        ).read_text()
    files["scripts/im_release/__init__.py"] = (
        '"""Vendored Integration Manager release contracts; update through a reviewed PR."""\n'
    )
    files["scripts/release.py"] = (
        (ROOT / "scripts/release.py")
        .read_text()
        .replace("custom_components.integration_manager.", "scripts.im_release.")
    )
    files["requirements-release.lock"] = (ROOT / "requirements-release.lock").read_text()
    collisions = [name for name in files if (target / name).exists()]
    if collisions:
        raise ManagerError(
            "Review existing files before installing the bundle: " + ", ".join(collisions)
        )
    written = []
    for name, content in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--domain", required=True)
    parser.add_argument(
        "--commands", type=Path, required=True, help="Reviewed project CI commands as JSON"
    )
    args = parser.parse_args()
    for path in prepare(args.target, args.domain, json.loads(args.commands.read_text())):
        print(path)
    print(
        "Review and merge these files through a PR; "
        "configure the documented owner-side permissions and secrets."
    )


if __name__ == "__main__":
    main()
