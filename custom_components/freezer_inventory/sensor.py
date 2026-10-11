"""Sensor for the Freezer Inventory integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FreezerInventory
from .const import ATTR_ITEMS, ATTR_QUANTITY, DOMAIN, EVENT_UPDATED


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the freezer sensor."""
    async_add_entities([FreezerSensor(hass.data[DOMAIN])])


class FreezerSensor(SensorEntity):
    """Total number of items in the freezer; item list in attributes."""

    _attr_should_poll = False
    _attr_name = "Freezer items"
    _attr_unique_id = f"{DOMAIN}_items"
    _attr_icon = "mdi:fridge-industrial-outline"

    def __init__(self, inventory: FreezerInventory) -> None:
        """Initialize."""
        self._inventory = inventory

    @property
    def native_value(self) -> int:
        """Return total quantity."""
        return sum(i[ATTR_QUANTITY] for i in self._inventory.items)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the item list."""
        return {
            ATTR_ITEMS: [dict(item) for item in self._inventory.items],
            "revision": self._inventory.revision,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to inventory updates."""

        @callback
        def _update(_event) -> None:
            self.async_write_ha_state()

        self.async_on_remove(self.hass.bus.async_listen(EVENT_UPDATED, _update))
