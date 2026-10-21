"""One native update entity per approved repository, added dynamically."""

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .models import ManagerError


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    manager = entry.runtime_data
    known = set()

    @callback
    def add_new():
        new = [domain for domain in manager.records if domain not in known]
        known.update(new)
        async_add_entities([IntegrationUpdate(manager, domain) for domain in new])

    entry.async_on_unload(manager.listen(add_new))
    add_new()


class IntegrationUpdate(UpdateEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "Update"
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.RELEASE_NOTES
        | UpdateEntityFeature.SPECIFIC_VERSION
    )

    def __init__(self, manager, domain: str) -> None:
        self.manager, self.domain = manager, domain
        self._attr_unique_id = f"{DOMAIN}_{manager.environment}_{domain}_update"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, domain)}, name=domain, manufacturer="Integration Manager"
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.manager.listen(self.async_write_ha_state))

    @property
    def available(self):
        return self.domain in self.manager.records

    @property
    def installed_version(self):
        record = self.manager.records.get(self.domain)
        return record.installed.version if record and record.installed else None

    @property
    def latest_version(self):
        record = self.manager.records.get(self.domain)
        return record.available.version if record and record.available else self.installed_version

    @property
    def release_url(self):
        record = self.manager.records.get(self.domain)
        return record.available.html_url if record and record.available else None

    @property
    def in_progress(self):
        record = self.manager.records.get(self.domain)
        return bool(record and 0 < record.progress < 100)

    @property
    def extra_state_attributes(self):
        record = self.manager.records.get(self.domain)
        return (
            {
                "running_version": record.running_version,
                "operation_state": record.state,
                "health": record.status()["health"],
                "error": record.error,
            }
            if record
            else {}
        )

    async def async_install(self, version, backup, **kwargs):
        if self._context and self._context.user_id:
            user = await self.hass.auth.async_get_user(self._context.user_id)
            if user is None or not user.is_admin:
                raise Unauthorized(context=self._context)
        try:
            await self.manager.install(self.domain, target_version=version)
        except ManagerError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_release_notes(self):
        record = self.manager.get(self.domain)
        return record.available.notes if record.available else "No eligible release"
