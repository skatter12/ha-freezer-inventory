"""The Freezer Inventory integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_BEST_BEFORE,
    ATTR_DATE_ADDED,
    ATTR_ITEMS,
    ATTR_NAME,
    ATTR_QUANTITY,
    ATTR_UNIT,
    DOMAIN,
    EVENT_UPDATED,
    SERVICE_ADD_ITEM,
    SERVICE_CLEAR,
    SERVICE_REMOVE_ITEM,
    STORAGE_KEY,
    STORAGE_VERSION,
)

PLATFORMS = ["sensor"]

ADD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_QUANTITY, default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(ATTR_UNIT): cv.string,
        vol.Optional(ATTR_BEST_BEFORE): cv.date,
    }
)
REMOVE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_QUANTITY): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)


class FreezerInventory:
    """Persistent freezer inventory."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass
        self.items: list[dict[str, Any]] = []
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> None:
        """Load items from storage."""
        data = await self._store.async_load()
        self.items = data[ATTR_ITEMS] if data else []

    @callback
    def _changed(self) -> None:
        self._store.async_delay_save(lambda: {ATTR_ITEMS: self.items}, 1)
        self.hass.bus.async_fire(EVENT_UPDATED)

    def _find(self, name: str) -> dict[str, Any] | None:
        key = name.strip().casefold()
        return next((i for i in self.items if i[ATTR_NAME].casefold() == key), None)

    @callback
    def async_add(
        self,
        name: str,
        quantity: int = 1,
        unit: str | None = None,
        best_before: str | None = None,
    ) -> None:
        """Add an item or increase its quantity."""
        item = self._find(name)
        if item is None:
            item = {
                ATTR_NAME: name.strip(),
                ATTR_QUANTITY: 0,
                ATTR_UNIT: unit,
                ATTR_DATE_ADDED: dt_util.now().date().isoformat(),
                ATTR_BEST_BEFORE: None,
            }
            self.items.append(item)
        item[ATTR_QUANTITY] += quantity
        if unit:
            item[ATTR_UNIT] = unit
        if best_before:
            item[ATTR_BEST_BEFORE] = best_before
        self._changed()

    @callback
    def async_remove(self, name: str, quantity: int | None = None) -> None:
        """Remove (part of) an item."""
        item = self._find(name)
        if item is None:
            return
        if quantity is None or quantity >= item[ATTR_QUANTITY]:
            self.items.remove(item)
        else:
            item[ATTR_QUANTITY] -= quantity
        self._changed()

    @callback
    def async_clear(self) -> None:
        """Remove all items."""
        self.items = []
        self._changed()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Freezer Inventory from a config entry."""
    inventory = FreezerInventory(hass)
    await inventory.async_load()
    hass.data[DOMAIN] = inventory

    async def add_item(call: ServiceCall) -> None:
        best_before = call.data.get(ATTR_BEST_BEFORE)
        inventory.async_add(
            call.data[ATTR_NAME],
            call.data[ATTR_QUANTITY],
            call.data.get(ATTR_UNIT),
            best_before.isoformat() if best_before else None,
        )

    async def remove_item(call: ServiceCall) -> None:
        inventory.async_remove(call.data[ATTR_NAME], call.data.get(ATTR_QUANTITY))

    async def clear(call: ServiceCall) -> None:
        inventory.async_clear()

    hass.services.async_register(DOMAIN, SERVICE_ADD_ITEM, add_item, ADD_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_ITEM, remove_item, REMOVE_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_CLEAR, clear)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    for service in (SERVICE_ADD_ITEM, SERVICE_REMOVE_ITEM, SERVICE_CLEAR):
        hass.services.async_remove(DOMAIN, service)
    hass.data.pop(DOMAIN)
    return True
