import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import jwt
import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.integration_manager.github import API, GitHubClient, GitHubError
from custom_components.integration_manager.models import ManagerError


def client(hass, pem):
    return GitHubClient(async_get_clientsession(hass), "123", "456", pem)


async def test_app_jwt_token_refresh_and_single_flight(hass, pem, aioclient_mock):
    expiry = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    aioclient_mock.post(
        f"{API}/app/installations/456/access_tokens",
        json={
            "token": "installation-placeholder",
            "expires_at": expiry,
            "permissions": {"contents": "read"},
        },
    )
    github = client(hass, pem)
    tokens = await asyncio.gather(*(github.token() for _ in range(5)))
    assert tokens == ["installation-placeholder"] * 5
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2]["permissions"] == {
        "contents": "read",
        "actions_variables": "write",
        "actions": "write",
    }
    assertion = aioclient_mock.mock_calls[0][3]["Authorization"].removeprefix("Bearer ")
    claims = jwt.decode(assertion, options={"verify_signature": False})
    assert claims["iss"] == "123" and claims["exp"] - claims["iat"] <= 600
    assert jwt.get_unverified_header(assertion)["alg"] == "RS256"
    github._expires = time.time()
    await github.token()
    assert aioclient_mock.call_count == 2


async def test_etag_pagination(hass, pem, aioclient_mock):
    github = client(hass, pem)
    github._token, github._expires = "cached", time.time() + 3600
    aioclient_mock.get(
        f"{API}/repos/THEFLDR/demo/releases?per_page=100&page=1",
        json=[{"id": 1, "draft": False}],
        headers={"ETag": '"revision"'},
    )
    assert (await github.releases("THEFLDR/demo"))[0]["id"] == 1
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API}/repos/THEFLDR/demo/releases?per_page=100&page=1", status=304)
    assert (await github.releases("THEFLDR/demo"))[0]["id"] == 1
    assert aioclient_mock.mock_calls[0][3]["If-None-Match"] == '"revision"'


async def test_status_size_permissions_and_creation(hass, pem):
    github = client(hass, pem)
    github.request = AsyncMock(side_effect=[GitHubError("PATCH", "/variables", 404), None])
    await github.write_status("THEFLDR/demo", "sandbox", {"schema_version": 1})
    assert [call.args[0] for call in github.request.call_args_list] == ["PATCH", "POST"]
    with pytest.raises(ManagerError, match="48 KB"):
        await github.write_status("THEFLDR/demo", "sandbox", {"oversized": "x" * (48 * 1024)})
    github.request = AsyncMock(side_effect=GitHubError("PATCH", "/variables", 403))
    with pytest.raises(GitHubError, match="403"):
        await github.write_status("THEFLDR/demo", "sandbox", {})
    assert github.request.call_count == 1


@pytest.mark.parametrize("payload", ["[]", "null", "{broken"])
async def test_malformed_registry_is_an_actionable_error(hass, pem, payload):
    github = client(hass, pem)
    github.request = AsyncMock(return_value={"value": payload})
    with pytest.raises(ManagerError, match="Invalid JSON"):
        await github.read_status("THEFLDR/demo", "production")


async def test_release_identity_and_digest(hass, pem, bundle):
    release, metadata, data = bundle()
    github = client(hass, pem)
    github.asset = AsyncMock(return_value=json.dumps(metadata).encode())
    github.commit = AsyncMock(return_value=release.commit)
    raw = {
        "id": release.release_id,
        "tag_name": release.tag,
        "draft": False,
        "immutable": True,
        "prerelease": True,
        "html_url": release.html_url,
        "assets": [
            {
                "name": "integration.zip",
                "id": release.asset_id,
                "digest": f"sha256:{release.sha256}",
                "size": len(data),
            },
            {"name": "integration.json", "id": 99},
        ],
    }
    result, _ = await github.release(release.repository, raw)
    assert result.identity() == release.identity()
    raw["assets"][0]["digest"] = "sha256:" + "0" * 64
    with pytest.raises(ManagerError, match="digest"):
        await github.release(release.repository, raw)


@pytest.mark.parametrize("payload", [b"{broken", b"[]", b"null", b'"string"', b"\xff"])
async def test_malformed_release_metadata_is_an_actionable_error(hass, pem, bundle, payload):
    release, _, _ = bundle()
    github = client(hass, pem)
    github.asset = AsyncMock(return_value=payload)
    raw = {
        "tag_name": release.tag,
        "immutable": True,
        "assets": [
            {"name": "integration.zip", "id": release.asset_id},
            {"name": "integration.json", "id": 99},
        ],
    }
    with pytest.raises(ManagerError, match="Release metadata"):
        await github.release(release.repository, raw)


async def test_bounded_asset_redirect_never_forwards_token(hass, pem, aioclient_mock):
    github = client(hass, pem)
    github._token, github._expires = "private-placeholder", time.time() + 3600
    url = "https://release-assets.githubusercontent.com/example/package.zip?signature=synthetic"
    aioclient_mock.get(
        f"{API}/repos/THEFLDR/demo/releases/assets/1", status=302, headers={"Location": url}
    )
    aioclient_mock.get(url, content=b"package")
    assert await github.asset("THEFLDR/demo", 1) == b"package"
    assert (
        aioclient_mock.mock_calls[-1][3] is None
        or "Authorization" not in aioclient_mock.mock_calls[-1][3]
    )


async def test_unexpected_redirect_and_override_rejected(hass, pem, aioclient_mock):
    github = client(hass, pem)
    github._token, github._expires = "cached", time.time() + 3600
    aioclient_mock.get(
        f"{API}/repos/THEFLDR/demo/releases/assets/1",
        status=302,
        headers={"Location": "https://attacker.example/package.zip"},
    )
    with pytest.raises(ManagerError, match="destination"):
        await github.asset("THEFLDR/demo", 1)
    with pytest.raises(ManagerError, match="normal promotion only"):
        await github.dispatch("THEFLDR/demo", "override.yml", {})
