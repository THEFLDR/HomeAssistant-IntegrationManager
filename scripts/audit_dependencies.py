#!/usr/bin/env python3
"""Audit every locked dependency, with visible, version-bound, expiring owner exceptions."""

import json

# Fixed executable/module/lock paths below; no shell or user-supplied arguments.
import subprocess  # nosec B404
import sys
from datetime import UTC, date, datetime
from pathlib import Path


def evaluate(
    report: dict, policy: dict, today: date, project_version="0.1.0"
) -> tuple[list[str], list[str]]:
    if policy.get("schema_version") != 1:
        raise ValueError("Unknown dependency exception schema")
    exceptions = policy["exceptions"]
    if exceptions and tuple(map(int, project_version.split("."))) >= (1, 0, 0):
        raise ValueError(
            "Sandbox dependency exceptions cannot be carried into a 1.0.0 Production release"
        )
    if exceptions and today >= date.fromisoformat(policy["expires_on"]):
        raise ValueError(
            "Temporary dependency exceptions expired; obtain fixed compatible Core pins"
        )
    accepted, rejected = [], []
    for dependency in report["dependencies"]:
        if "skip_reason" in dependency:
            rejected.append(f"Dependency was not audited: {dependency['name']}")
        for advisory in dependency.get("vulns", []):
            ids = {advisory["id"], *advisory.get("aliases", [])}
            label = f"{dependency['name']}=={dependency['version']}: {advisory['id']}"
            if any(
                e["package"] == dependency["name"]
                and e["version"] == dependency["version"]
                and e["id"] in ids
                for e in exceptions
            ):
                accepted.append(label)
            else:
                rejected.append(label)
    return accepted, rejected


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    # All transitive requirements are exact lock pins. Installation already verifies their hashes.
    # Scan every pin directly; avoid a second installation/resolution during the same CI run.
    command = [
        sys.executable,
        "-m",
        "pip_audit",
        "--require-hashes",
        "--no-deps",
        "--disable-pip",
        "-r",
        str(root / "requirements-dev.lock"),
        "--format",
        "json",
        "--progress-spinner",
        "off",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603 # nosec B603
    if result.returncode not in (0, 1):
        print(result.stderr, file=sys.stderr)
        return result.returncode
    try:
        report = json.loads(result.stdout)
        policy = json.loads((root / "security/dependency-exceptions.json").read_text())
        manifest = json.loads(
            (root / "custom_components/integration_manager/manifest.json").read_text()
        )
        accepted, rejected = evaluate(report, policy, datetime.now(UTC).date(), manifest["version"])
    except (ValueError, KeyError, TypeError) as err:
        print(f"Dependency audit could not be validated: {err}", file=sys.stderr)
        return 1
    print(f"Audited {len(report['dependencies'])} exact dependency pins")
    for message in accepted:
        print(f"OWNER-ACCEPTED UNTIL {policy['expires_on']}: {message}")
    for message in rejected:
        print(f"REJECTED: {message}", file=sys.stderr)
    if result.returncode == 1 and not accepted and not rejected:
        print("Audit command failed without a vulnerability report", file=sys.stderr)
        return 1
    return int(bool(rejected))


if __name__ == "__main__":
    sys.exit(main())
