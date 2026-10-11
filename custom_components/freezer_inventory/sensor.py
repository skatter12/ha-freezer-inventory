"""Sensor for the Freezer Inventory integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FreezerInventory
from .const import (
    ATTR_ITEMS,
    ATTR_LOCATION,
    CONF_FREEZER_TEMP,
    CONF_FRIDGE_TEMP,
    ATTR_QUANTITY,
    DOMAIN,
    EVENT_UPDATED,
    LOCATION_FREEZER,
    LOCATION_FRIDGE,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the freezer sensor."""
    inventory = hass.data[DOMAIN]
    conf = {**entry.data, **entry.options}
    async_add_entities(
        [
            InventorySensor(inventory, LOCATION_FREEZER, "Freezer items", "mdi:fridge-industrial-outline", f"{DOMAIN}_items", conf.get(CONF_FREEZER_TEMP)),
            InventorySensor(inventory, LOCATION_FRIDGE, "Fridge items", "mdi:fridge-outline", f"{DOMAIN}_fridge_items", conf.get(CONF_FRIDGE_TEMP)),
        ]
    )


class InventorySensor(SensorEntity):
    """Total number of packages in a location; item list in attributes."""

    _attr_should_poll = False

    def __init__(
        self,
        inventory: FreezerInventory,
        location: str,
        name: str,
        icon: str,
        unique_id: str,
        temperature_entity: str | None = None,
    ) -> None:
        """Initialize."""
        self._inventory = inventory
        self._location = location
        self._temperature_entity = temperature_entity
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = unique_id

    def _items(self) -> list[dict]:
        return [i for i in self._inventory.items if i[ATTR_LOCATION] == self._location]

    @property
    def native_value(self) -> int:
        """Return total quantity."""
        return sum(i[ATTR_QUANTITY] for i in self._items())

    @property
    def extra_state_attributes(self) -> dict:
        """Return the item list."""
        return {
            ATTR_ITEMS: [dict(item) for item in self._items()],
            "revision": self._inventory.revision,
            "temperature_entity": self._temperature_entity,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to inventory updates."""

        @callback
        def _update(_event) -> None:
            self.async_write_ha_state()

        self.async_on_remove(self.hass.bus.async_listen(EVENT_UPDATED, _update))
