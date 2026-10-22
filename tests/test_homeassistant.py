import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import loader
from homeassistant.components import websocket_api
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.integration_manager.config_flow import write_key
from custom_components.integration_manager.const import DOMAIN
from custom_components.integration_manager.panel import (
    websocket_action,
    websocket_status,
    websocket_subscribe,
)


async def test_manifest_loader_and_initial_config_flow(hass, pem, tmp_path):
    integration = await loader.async_get_integration(hass, DOMAIN)
    assert integration.version == "0.1.0"
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert flow["type"] == "form"
    key_path = tmp_path / "keys/test.pem"
    with (
        patch("custom_components.integration_manager.config_flow.validate_connection", AsyncMock()),
        patch(
            "custom_components.integration_manager.config_flow.write_key",
            return_value=str(key_path),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {
                "app_id": "123",
                "client_id": "client-example",
                "installation_id": "456",
                "private_key": pem,
                "environment": "sandbox",
                "registry_repository": "ThEfLdR/HoMeAsSiStAnT-InTeGrAtIoNmAnAgEr",
            },
        )
    assert result["type"] == "create_entry"
    assert "private_key" not in result["data"]
    assert result["data"]["key_path"] == str(key_path)
    assert result["data"]["instance_id"]
    assert result["data"]["registry_repository"] == "thefldr/homeassistant-integrationmanager"
    await hass.async_block_till_done()


async def test_production_config_blocked_before_one(hass):
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {
            "app_id": "123",
            "client_id": "example",
            "installation_id": "456",
            "private_key": "unused",
            "environment": "production",
            "registry_repository": "THEFLDR/HomeAssistant-IntegrationManager",
        },
    )
    assert result["type"] == "abort" and result["reason"] == "production_before_one"


def test_key_private_permissions_and_invalid_key(tmp_path, pem):
    path = tmp_path / "keys/app.pem"
    assert write_key(path, pem) == str(path)
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError):
        write_key(path, "not a key")
    assert path.read_text() == pem


async def test_options_key_is_not_in_entry(hass, pem, tmp_path):
    path = tmp_path / "key.pem"
    path.write_text(pem)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            "app_id": "123",
            "client_id": "example",
            "installation_id": "456",
            "key_path": str(path),
            "environment": "sandbox",
            "registry_repository": "THEFLDR/HomeAssistant-IntegrationManager",
            "instance_id": "test",
        },
    )
    entry.add_to_hass(hass)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    with patch(
        "custom_components.integration_manager.config_flow.validate_connection", AsyncMock()
    ):
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"app_id": "123", "client_id": "changed", "installation_id": "456"}
        )
    assert result["type"] == "create_entry" and "private_key" not in result["data"]


async def test_real_websocket_authorization_and_subscription(
    hass, manager, hass_ws_client, hass_admin_user
):
    hass.data[DOMAIN] = manager
    websocket_api.async_register_command(hass, websocket_status)
    websocket_api.async_register_command(hass, websocket_action)
    websocket_api.async_register_command(hass, websocket_subscribe)
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": "integration_manager/status"})
    result = await ws.receive_json()
    assert result["success"] and result["result"]["environment"] == "sandbox"
    await ws.send_json_auto_id({"type": "integration_manager/subscribe"})
    assert (await ws.receive_json())["success"]
    manager.notify()
    event = await ws.receive_json()
    assert event["type"] == "event" and event["event"]["environment"] == "sandbox"
    hass_admin_user.groups = []
    hass_admin_user.invalidate_cache()
    await ws.send_json_auto_id({"type": "integration_manager/action", "action": "restart"})
    denied = await ws.receive_json()
    assert not denied["success"] and denied["error"]["code"] == "unauthorized"
    await ws.close()


async def test_full_ha_setup_native_entities_panel_and_unload(
    hass, github, bundle, pem, tmp_path, entity_registry, hass_client, hass_ws_client
):
    config_dir = tmp_path / "ha"
    await hass.async_add_executor_job(config_dir.mkdir)
    hass.config.config_dir = str(config_dir)
    path = tmp_path / "key.pem"
    path.write_text(pem)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            "app_id": "123",
            "client_id": "example",
            "installation_id": "456",
            "key_path": str(path),
            "environment": "sandbox",
            "registry_repository": "THEFLDR/HomeAssistant-IntegrationManager",
            "instance_id": "test",
        },
    )
    entry.add_to_hass(hass)
    with patch("custom_components.integration_manager.github.GitHubClient", return_value=github):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    manager = entry.runtime_data
    sensor_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_sandbox_{DOMAIN}_health"
    )
    update_id = entity_registry.async_get_entity_id(
        "update", DOMAIN, f"{DOMAIN}_sandbox_{DOMAIN}_update"
    )
    assert sensor_id and update_id
    assert hass.states.get(sensor_id).state == "unknown"
    assert hass.states.get(update_id).attributes["running_version"] == "0.1.0"
    assert manager.interfaces_ready
    assert hass.services.has_service(DOMAIN, "report_health")
    assert manager.interfaces_healthy()
    http = await hass_client()
    response = await http.get("/integration_manager_static/panel.js")
    assert response.status == 200 and "customElements.define" in await response.text()
    logo = await http.get("/integration_manager_static/logo.png")
    assert logo.status == 200 and (await logo.read()).startswith(b"\x89PNG")
    github.add(bundle())
    await manager.register("ThEfLdR/DeMo", "demo", True)
    await hass.async_block_till_done()
    demo_update = entity_registry.async_get_entity_id(
        "update", DOMAIN, f"{DOMAIN}_sandbox_demo_update"
    )
    assert demo_update
    entered, resume = asyncio.Event(), asyncio.Event()
    asset = github.asset

    async def paused_asset(repo, asset_id):
        entered.set()
        await resume.wait()
        return await asset(repo, asset_id)

    github.asset = paused_asset
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id(
        {"type": "integration_manager/action", "action": "install", "domain": "demo"}
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        assert hass.states.get(demo_update).attributes["in_progress"] is True
    finally:
        resume.set()
        result = await ws.receive_json()
        await ws.close()
    assert result["success"], result
    assert hass.states.get(demo_update).attributes["in_progress"] is False
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not hass.services.has_service(DOMAIN, "report_health")


async def test_native_update_blocks_non_admin(hass, manager, hass_read_only_user):
    from homeassistant.core import Context
    from homeassistant.exceptions import Unauthorized

    from custom_components.integration_manager.update import IntegrationUpdate

    entity = IntegrationUpdate(manager, DOMAIN)
    entity.hass = hass
    entity.async_set_context(Context(user_id=hass_read_only_user.id))
    with pytest.raises(Unauthorized):
        await entity.async_install(None, False)


async def test_startup_offline_keeps_cached_releases_and_management_panel(
    hass, manager, github, bundle, pem, tmp_path
):
    from custom_components.integration_manager.models import ManagerError

    github.add(bundle())
    await manager.register("THEFLDR/demo", "demo", True)
    previous_check = manager.last_check
    await manager.save()
    github.validate.side_effect = ManagerError("GitHub unavailable")
    path = tmp_path / "key.pem"
    path.write_text(pem)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            **manager.config,
            "app_id": "123",
            "client_id": "example",
            "installation_id": "456",
            "key_path": str(path),
        },
    )
    entry.add_to_hass(hass)
    with patch("custom_components.integration_manager.github.GitHubClient", return_value=github):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    restored = entry.runtime_data
    assert restored.get("demo").available.version == "0.1.0"
    assert restored.last_check == previous_check
    assert restored.error == "GitHub unavailable"
    assert restored.interfaces_healthy()
    assert hass.services.has_service(DOMAIN, "report_health")
    assert await hass.config_entries.async_unload(entry.entry_id)
