"""Real HA fixtures with mocked outgoing GitHub; no credentials or HA instances needed."""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from custom_components.integration_manager.artifacts import build_package
from custom_components.integration_manager.manager import Manager
from custom_components.integration_manager.models import Release

REGISTRY = "THEFLDR/HomeAssistant-IntegrationManager"


@pytest.fixture(autouse=True)
def enable_integrations(enable_custom_integrations):
    """Allow loading the custom integration under the installed stable HA Core."""


@pytest.fixture
def pem():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


@pytest.fixture
def bundle(tmp_path):
    def make(domain="demo", ver="0.1.0", prerelease=True, repo="THEFLDR/demo", rid=10):
        source = tmp_path / "sources" / f"{domain}-{ver}"
        source.mkdir(parents=True, exist_ok=True)
        (source / "manifest.json").write_text(
            json.dumps(
                {
                    "domain": domain,
                    "name": "Demo",
                    "version": ver,
                    "requirements": [],
                    "config_flow": False,
                    "codeowners": [],
                }
            )
        )
        (source / "__init__.py").write_text('"""A managed test integration."""\n')
        data, metadata = build_package(source, domain)
        release = Release(
            repo,
            rid,
            f"v{ver}",
            ver,
            "a" * 40,
            rid + 100,
            metadata["sha256"],
            prerelease,
            True,
            f"https://github.com/{repo}/releases/tag/v{ver}",
        )
        return release, metadata, data

    return make


class FakeGitHub:
    def __init__(self):
        self.permissions = {"contents": "read", "actions_variables": "write", "actions": "write"}
        self.bundles = {}
        self.statuses = {}
        self.writes = []
        self.validate = AsyncMock()
        self.dispatch = AsyncMock()

    def add(self, bundle):
        release, metadata, data = bundle
        self.bundles[release.release_id] = (release, metadata, data)

    async def releases(self, repo):
        return [
            {
                "id": r.release_id,
                "tag_name": r.tag,
                "prerelease": r.prerelease,
                "draft": False,
                "immutable": True,
            }
            for r, _, _ in self.bundles.values()
            if r.repository == repo
        ]

    async def request(self, method, path, **kwargs):
        if "/releases/" in path:
            rid = int(path.rsplit("/", 1)[1])
            r = self.bundles[rid][0]
            return {"id": rid, "tag_name": r.tag, "prerelease": r.prerelease}
        return {"archived": False, "disabled": False, "default_branch": "main"}

    async def release(self, repo, raw):
        release, metadata, _ = self.bundles[raw["id"]]
        return deepcopy(release), deepcopy(metadata)

    async def asset(self, repo, asset_id):
        return next(data for r, _, data in self.bundles.values() if r.asset_id == asset_id)

    async def read_status(self, registry, environment):
        return deepcopy(self.statuses.get(environment, {}))

    async def write_status(self, registry, environment, document):
        self.statuses[environment] = deepcopy(document)
        self.writes.append((environment, deepcopy(document)))


@pytest.fixture
def github():
    return FakeGitHub()


@pytest.fixture
async def manager(hass, github, tmp_path, monkeypatch):
    hass.config.config_dir = str(tmp_path / "ha")
    await hass.async_add_executor_job(Path(hass.config.config_dir).mkdir)
    config = {
        "environment": "sandbox",
        "registry_repository": REGISTRY,
        "instance_id": "sandbox-test",
    }
    manager = Manager(hass, github, config)
    await manager.load()
    manager.interfaces_ready = True
    # Unit tests replace interface probing; the full HA setup test uses real entities/services.
    monkeypatch.setattr(manager, "interfaces_healthy", lambda: True)
    yield manager
    await manager.close()


@pytest.fixture
def loaded(hass):
    def apply(domain, ver):
        from unittest.mock import MagicMock

        hass.config.components.add(domain)
        integration = MagicMock(version=ver)
        return patch(
            "custom_components.integration_manager.manager.loader.async_get_loaded_integration",
            return_value=integration,
        )

    return apply
