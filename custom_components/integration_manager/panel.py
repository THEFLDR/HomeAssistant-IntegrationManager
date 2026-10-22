"""Supported custom panel plus server-authorized WebSocket and health service."""

from pathlib import Path

import voluptuous as vol
from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN
from .models import ManagerError


async def async_setup_panel(hass, manager) -> None:
    if not hass.data.get(f"{DOMAIN}_static"):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    "/integration_manager_static", str(Path(__file__).parent / "frontend"), False
                )
            ]
        )
        hass.data[f"{DOMAIN}_static"] = True
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="integration-manager-panel",
        frontend_url_path=DOMAIN,
        sidebar_title="Integration Manager",
        sidebar_icon="mdi:package-variant",
        module_url="/integration_manager_static/panel.js",
        require_admin=True,
        config={"environment": manager.environment},
    )
    websocket_api.async_register_command(hass, websocket_status)
    websocket_api.async_register_command(hass, websocket_action)
    websocket_api.async_register_command(hass, websocket_subscribe)

    async def health(call):
        await manager.report_health(**call.data)

    async_register_admin_service(
        hass,
        DOMAIN,
        "report_health",
        health,
        schema=vol.Schema(
            {
                vol.Required("domain"): str,
                vol.Required("health"): vol.In(["healthy", "unhealthy"]),
                vol.Required("reported_version"): str,
                vol.Required("release_id"): vol.Coerce(int),
                vol.Required("sha256"): str,
            }
        ),
    )


@websocket_api.websocket_command({vol.Required("type"): "integration_manager/status"})
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_status(hass, connection, msg):
    manager = hass.data.get(DOMAIN)
    if not manager:
        connection.send_error(msg["id"], "not_loaded", "Integration Manager is not loaded")
        return
    connection.send_result(msg["id"], manager.snapshot())


@websocket_api.websocket_command({vol.Required("type"): "integration_manager/subscribe"})
@websocket_api.require_admin
def websocket_subscribe(hass, connection, msg):
    manager = hass.data.get(DOMAIN)
    if not manager:
        connection.send_error(msg["id"], "not_loaded", "Integration Manager is not loaded")
        return

    def changed():
        connection.send_event(msg["id"], manager.snapshot())

    connection.subscriptions[msg["id"]] = manager.listen(changed)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "integration_manager/action",
        vol.Required("action"): vol.In(
            [
                "check",
                "register",
                "install",
                "adopt",
                "uninstall",
                "restore",
                "promote",
                "confirm_absent",
                "restart",
            ]
        ),
        vol.Optional("domain", default=""): str,
        vol.Optional("repository", default=""): str,
        vol.Optional("confirmation", default=""): str,
        vol.Optional("approved", default=False): bool,
        vol.Optional("version"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_action(hass, connection, msg):
    manager = hass.data.get(DOMAIN)
    if not manager:
        connection.send_error(msg["id"], "not_loaded", "Integration Manager is not loaded")
        return
    try:
        action, domain = msg["action"], msg["domain"]
        if action == "check":
            await manager.check()
        elif action == "register":
            await manager.register(msg["repository"], domain, msg["approved"])
        elif action in ("install", "adopt"):
            await manager.install(
                domain, adopt=action == "adopt", target_version=msg.get("version")
            )
        elif action in ("uninstall", "restore", "confirm_absent"):
            await getattr(manager, action)(domain, msg["confirmation"])
        elif action == "promote":
            await manager.promote(domain)
        elif action == "restart":
            if msg["confirmation"] != "restart Home Assistant":
                raise ManagerError("Explicit restart confirmation is required")
            await hass.services.async_call(
                "homeassistant", "restart", blocking=False, context=connection.context(msg)
            )
        connection.send_result(msg["id"], {"accepted": True})
    except ManagerError as err:
        connection.send_error(msg["id"], "operation_failed", str(err))
