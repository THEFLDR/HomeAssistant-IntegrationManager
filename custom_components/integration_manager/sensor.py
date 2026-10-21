"""A single health sensor per integration with version and operation attributes."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    manager = entry.runtime_data
    known = set()

    @callback
    def add_new():
        new = [domain for domain in manager.records if domain not in known]
        known.update(new)
        async_add_entities([IntegrationHealth(manager, domain) for domain in new])

    entry.async_on_unload(manager.listen(add_new))
    add_new()


class IntegrationHealth(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "Health"
    _attr_icon = "mdi:heart-pulse"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager, domain):
        self.manager, self.domain = manager, domain
        self._attr_unique_id = f"{DOMAIN}_{manager.environment}_{domain}_health"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, domain)}, name=domain, manufacturer="Integration Manager"
        )

    async def async_added_to_hass(self):
        self.async_on_remove(self.manager.listen(self.async_write_ha_state))

    @property
    def available(self):
        return self.domain in self.manager.records

    @property
    def native_value(self):
        record = self.manager.records.get(self.domain)
        return record.status()["health"] if record else "unknown"

    @property
    def extra_state_attributes(self):
        record = self.manager.records.get(self.domain)
        return (
            record.status() | {"error": record.error, "checked_at": record.checked_at}
            if record
            else {}
        )
