"""The Freezer Inventory integration."""
from __future__ import annotations

from pathlib import Path
import math
from typing import Any

import voluptuous as vol

from homeassistant.components import frontend, panel_custom
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_AMOUNT,
    ATTR_BEST_BEFORE,
    ATTR_DATE_ADDED,
    ATTR_ITEMS,
    ATTR_NAME,
    ATTR_PACKAGE_SIZE,
    ATTR_QUANTITY,
    ATTR_REMAINING,
    ATTR_UNIT,
    ATTR_UNITS,
    DOMAIN,
    EVENT_UPDATED,
    SERVICE_ADD_ITEM,
    SERVICE_CLEAR,
    SERVICE_REMOVE_ITEM,
    SERVICE_SET_QUANTITY,
    SERVICE_SET_UNITS,
    SERVICE_USE_AMOUNT,
    STORAGE_KEY,
    STORAGE_VERSION,
)

PLATFORMS = ["sensor"]

PANEL_URL_PATH = "freezer-inventory"
PANEL_STATIC_URL = "/freezer_inventory_static/freezer-inventory-panel.js"
PANEL_VERSION = "0.4.0"
PANEL_FILE = Path(__file__).parent / "frontend" / "freezer-inventory-panel.js"

ADD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_QUANTITY, default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(ATTR_UNIT): cv.string,
        vol.Optional(ATTR_PACKAGE_SIZE): vol.All(
            vol.Coerce(float), vol.Range(min=0, min_included=False)
        ),
        vol.Optional(ATTR_BEST_BEFORE): cv.date,
    }
)
SET_UNITS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_UNITS): vol.All(vol.Coerce(float), vol.Range(min=0)),
    }
)
USE_AMOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_AMOUNT): vol.All(
            vol.Coerce(float), vol.Range(min=0, min_included=False)
        ),
    }
)
SET_QUANTITY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_QUANTITY): vol.All(vol.Coerce(int), vol.Range(min=0)),
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
        self.revision = 0
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> None:
        """Load items from storage."""
        data = await self._store.async_load()
        self.items = data[ATTR_ITEMS] if data else []

    @callback
    def _changed(self) -> None:
        self.revision += 1
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
        package_size: float | None = None,
    ) -> None:
        """Add an item or increase its quantity."""
        item = self._find(name)
        if item is None:
            item = {
                ATTR_NAME: name.strip(),
                ATTR_QUANTITY: 0,
                ATTR_UNIT: unit,
                ATTR_PACKAGE_SIZE: None,
                ATTR_REMAINING: None,
                ATTR_DATE_ADDED: dt_util.now().date().isoformat(),
                ATTR_BEST_BEFORE: None,
            }
            self.items.append(item)
        item[ATTR_QUANTITY] += quantity
        if unit:
            item[ATTR_UNIT] = unit
        if package_size:
            if item.get(ATTR_PACKAGE_SIZE) != package_size:
                item[ATTR_PACKAGE_SIZE] = package_size
                item[ATTR_REMAINING] = package_size
        if item.get(ATTR_PACKAGE_SIZE) and item.get(ATTR_REMAINING) is None:
            item[ATTR_REMAINING] = item[ATTR_PACKAGE_SIZE]
        if best_before:
            item[ATTR_BEST_BEFORE] = best_before
        self._changed()

    @callback
    def async_use_amount(self, name: str, amount: float) -> None:
        """Use part of the contents; opens the next package when one is used up."""
        item = self._find(name)
        if item is None or not item.get(ATTR_PACKAGE_SIZE):
            return
        size = item[ATTR_PACKAGE_SIZE]
        remaining = item.get(ATTR_REMAINING)
        if remaining is None:
            remaining = size
        while amount > 1e-9 and item[ATTR_QUANTITY] > 0:
            if amount < remaining - 1e-9:
                remaining = round(remaining - amount, 6)
                amount = 0
            else:
                amount = round(amount - remaining, 6)
                item[ATTR_QUANTITY] -= 1
                remaining = size
        if item[ATTR_QUANTITY] <= 0:
            self.items.remove(item)
        else:
            item[ATTR_REMAINING] = remaining
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
    def async_set_units(self, name: str, units: float) -> None:
        """Set the total units; packages are recalculated (last one may be partial)."""
        item = self._find(name)
        if item is None or not item.get(ATTR_PACKAGE_SIZE):
            return
        size = item[ATTR_PACKAGE_SIZE]
        if units <= 1e-9:
            self.items.remove(item)
        else:
            packages = math.ceil(units / size - 1e-9)
            item[ATTR_QUANTITY] = packages
            item[ATTR_REMAINING] = round(units - (packages - 1) * size, 6)
        self._changed()

    @callback
    def async_set_quantity(self, name: str, quantity: int) -> None:
        """Set the number of packages (0 removes the item)."""
        item = self._find(name)
        if item is None:
            return
        if quantity <= 0:
            self.items.remove(item)
        else:
            item[ATTR_QUANTITY] = quantity
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
            call.data.get(ATTR_PACKAGE_SIZE),
        )

    async def set_units(call: ServiceCall) -> None:
        inventory.async_set_units(call.data[ATTR_NAME], call.data[ATTR_UNITS])

    async def use_amount(call: ServiceCall) -> None:
        inventory.async_use_amount(call.data[ATTR_NAME], call.data[ATTR_AMOUNT])

    async def remove_item(call: ServiceCall) -> None:
        inventory.async_remove(call.data[ATTR_NAME], call.data.get(ATTR_QUANTITY))

    async def set_quantity(call: ServiceCall) -> None:
        inventory.async_set_quantity(call.data[ATTR_NAME], call.data[ATTR_QUANTITY])

    async def clear(call: ServiceCall) -> None:
        inventory.async_clear()

    hass.services.async_register(DOMAIN, SERVICE_ADD_ITEM, add_item, ADD_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_ITEM, remove_item, REMOVE_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_CLEAR, clear)
    hass.services.async_register(
        DOMAIN, SERVICE_SET_UNITS, set_units, SET_UNITS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_USE_AMOUNT, use_amount, USE_AMOUNT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_QUANTITY, set_quantity, SET_QUANTITY_SCHEMA
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_register_panel(hass)
    return True


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Serve the panel JS and add it to the sidebar."""
    from homeassistant.components.http import StaticPathConfig

    if not hass.data.get(f"{DOMAIN}_static_registered"):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_STATIC_URL, str(PANEL_FILE), False)]
        )
        hass.data[f"{DOMAIN}_static_registered"] = True
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="freezer-inventory-panel",
        frontend_url_path=PANEL_URL_PATH,
        module_url=f"{PANEL_STATIC_URL}?v={PANEL_VERSION}",
        sidebar_title="Freezer",
        sidebar_icon="mdi:fridge-industrial-outline",
        require_admin=False,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    for service in (
        SERVICE_ADD_ITEM,
        SERVICE_REMOVE_ITEM,
        SERVICE_SET_QUANTITY,
        SERVICE_SET_UNITS,
        SERVICE_USE_AMOUNT,
        SERVICE_CLEAR,
    ):
        hass.services.async_remove(DOMAIN, service)
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    hass.data.pop(DOMAIN)
    return True
