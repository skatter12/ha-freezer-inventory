"""Sensors for the Freezer Inventory integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FreezerInventory
from .const import (
    ATTR_APPLIANCE,
    ATTR_ITEMS,
    ATTR_LOCATION,
    ATTR_QUANTITY,
    CONF_FREEZER_TEMP,
    CONF_FRIDGE_TEMP,
    DOMAIN,
    EVENT_UPDATED,
    LOCATION_FREEZER,
    LOCATION_FRIDGE,
)

APPLIANCE_PREFIX = f"{DOMAIN}_appliance_"
ICONS = {
    LOCATION_FREEZER: "mdi:fridge-industrial-outline",
    LOCATION_FRIDGE: "mdi:fridge-outline",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors: the default freezer and fridge plus any extra ones."""
    inventory: FreezerInventory = hass.data[DOMAIN]
    conf = {**entry.data, **entry.options}
    sensors = [
        InventorySensor(
            inventory,
            LOCATION_FREEZER,
            None,
            "Freezer items",
            f"{DOMAIN}_items",
            conf.get(CONF_FREEZER_TEMP),
        ),
        InventorySensor(
            inventory,
            LOCATION_FRIDGE,
            None,
            "Fridge items",
            f"{DOMAIN}_fridge_items",
            conf.get(CONF_FRIDGE_TEMP),
        ),
    ]
    for appliance in inventory.appliances:
        sensors.append(
            InventorySensor(
                inventory,
                appliance["kind"],
                appliance["id"],
                f"{appliance['name']} items",
                f"{APPLIANCE_PREFIX}{appliance['id']}",
                appliance.get("temperature_entity"),
            )
        )

    # Drop sensors of freezers/fridges that were deleted.
    current = {sensor.unique_id for sensor in sensors}
    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            reg_entry.unique_id.startswith(APPLIANCE_PREFIX)
            and reg_entry.unique_id not in current
        ):
            registry.async_remove(reg_entry.entity_id)

    async_add_entities(sensors)


class InventorySensor(SensorEntity):
    """Total number of packages in one freezer or fridge; items in attributes."""

    _attr_should_poll = False

    def __init__(
        self,
        inventory: FreezerInventory,
        location: str,
        appliance_id: str | None,
        name: str,
        unique_id: str,
        temperature_entity: str | None = None,
    ) -> None:
        """Initialize."""
        self._inventory = inventory
        self._location = location
        self._appliance_id = appliance_id
        self._temperature_entity = temperature_entity
        self._attr_name = name
        self._attr_icon = ICONS[location]
        self._attr_unique_id = unique_id
        if appliance_id:
            self.entity_id = f"sensor.{DOMAIN}_{appliance_id}"

    def _items(self) -> list[dict]:
        return [
            i
            for i in self._inventory.items
            if i[ATTR_LOCATION] == self._location
            and i.get(ATTR_APPLIANCE) == self._appliance_id
        ]

    @property
    def native_value(self) -> int:
        """Return total quantity."""
        return sum(i[ATTR_QUANTITY] for i in self._items())

    @property
    def extra_state_attributes(self) -> dict:
        """Return the item list and the configured freezers/fridges."""
        return {
            ATTR_ITEMS: [dict(item) for item in self._items()],
            "revision": self._inventory.revision,
            "temperature_entity": self._temperature_entity,
            "appliances": [
                {"id": a["id"], "kind": a["kind"], "name": a["name"]}
                for a in self._inventory.appliances
            ],
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to inventory updates."""

        @callback
        def _update(_event) -> None:
            self.async_write_ha_state()

        self.async_on_remove(self.hass.bus.async_listen(EVENT_UPDATED, _update))
