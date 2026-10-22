#!/usr/bin/env python3
"""Cheap repository/package/workflow contracts, also run on documentation-only PRs."""

import json
import sys
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.integration_manager.artifacts import build_package, inspect_package  # noqa: E402
from custom_components.integration_manager.const import VERSION  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def check(*, light=False):
    for path in ROOT.rglob("*.json"):
        if any(part.startswith(".") for part in path.relative_to(ROOT).parts):
            continue
        json.loads(path.read_text())
    integration = ROOT / "custom_components/integration_manager"
    manifest = json.loads((integration / "manifest.json").read_text())
    require(manifest["version"] == VERSION, "Manifest/runtime versions differ")
    require(
        (integration / "translations/en.json").read_bytes()
        == (integration / "strings.json").read_bytes(),
        "English translation differs from strings",
    )
    original = sha256((ROOT / "approved-icon.png").read_bytes()).digest()
    for image in ("brand/icon.png", "frontend/logo.png"):
        require(
            sha256((integration / image).read_bytes()).digest() == original,
            "Approved logo differs from packaged branding",
        )
    rules = json.loads((ROOT / "docs/github/main-ruleset.json").read_text())
    required = next(r for r in rules["rules"] if r["type"] == "required_status_checks")
    require(
        required["parameters"]["required_status_checks"] == [{"context": "CI / Validation"}],
        "Ruleset must require exactly CI / Validation",
    )
    if light:
        print("Lightweight documentation/repository validation passed")
        return
    data, metadata = build_package(integration, manifest["domain"])
    require(bool(inspect_package(data, metadata)["manifest.json"]), "Manifest missing from package")
    require(
        build_package(integration, manifest["domain"])[0] == data, "Packaging is not deterministic"
    )
    print(f"Package, branding, translations and ruleset validated: {metadata['sha256']}")


if __name__ == "__main__":
    check(light="--light" in sys.argv)
