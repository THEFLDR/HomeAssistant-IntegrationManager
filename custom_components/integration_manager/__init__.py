"""Integration Manager lifecycle. Workflow-shared modules do not import HA at import time."""

from __future__ import annotations


async def async_setup_entry(hass, entry) -> bool:
    from pathlib import Path

    from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
    from homeassistant.exceptions import ConfigEntryNotReady
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    from homeassistant.helpers.event import async_track_time_interval

    from .const import CHECK_INTERVAL, DOMAIN, HEARTBEAT_INTERVAL
    from .github import GitHubClient
    from .manager import Manager
    from .models import ManagerError
    from .panel import async_setup_panel

    config = {**entry.data, **entry.options}
    try:
        key = await hass.async_add_executor_job(Path(config["key_path"]).read_text)
        client = GitHubClient(
            async_get_clientsession(hass), config["app_id"], config["installation_id"], key
        )
        manager = Manager(hass, client, config)
        await manager.load()
    except ManagerError as err:
        raise ConfigEntryNotReady(str(err)) from err
    except (OSError, ValueError) as err:
        raise ConfigEntryNotReady(
            "Cannot initialize Integration Manager; check config and GitHub access"
        ) from err
    entry.runtime_data = manager
    hass.data[DOMAIN] = manager
    await async_setup_panel(hass, manager)
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.UPDATE, Platform.SENSOR])
    manager.interfaces_ready = True
    entry.async_on_unload(async_track_time_interval(hass, manager.check, CHECK_INTERVAL))
    entry.async_on_unload(async_track_time_interval(hass, manager.heartbeat, HEARTBEAT_INTERVAL))
    entry.async_on_unload(entry.add_update_listener(_reload))

    async def started(_event=None):
        await manager.check()

    if hass.is_running:
        await started()
    else:
        entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, started))
    return True


async def _reload(hass, entry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry) -> bool:
    from homeassistant.components import frontend
    from homeassistant.const import Platform

    from .const import DOMAIN

    if not await hass.config_entries.async_unload_platforms(
        entry, [Platform.UPDATE, Platform.SENSOR]
    ):
        return False
    await entry.runtime_data.close()
    entry.runtime_data.interfaces_ready = False
    frontend.async_remove_panel(hass, DOMAIN)
    hass.services.async_remove(DOMAIN, "report_health")
    hass.data.pop(DOMAIN, None)
    return True
