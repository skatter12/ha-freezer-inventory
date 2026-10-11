"""The Freezer Inventory integration."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any
import uuid

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
    ATTR_ID,
    ATTR_ITEMS,
    ATTR_LOCATION,
    ATTR_NAME,
    ATTR_PACKAGE_SIZE,
    ATTR_QUANTITY,
    ATTR_REMAINING,
    ATTR_UNITS,
    DOMAIN,
    EVENT_UPDATED,
    LOCATION_FREEZER,
    LOCATIONS,
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
PANEL_VERSION = "0.9.0"
PANEL_FILE = Path(__file__).parent / "frontend" / "freezer-inventory-panel.js"

LOCATION = vol.All(vol.Lower, vol.In(LOCATIONS))
POSITIVE_FLOAT = vol.All(vol.Coerce(float), vol.Range(min=0, min_included=False))
NON_NEGATIVE_FLOAT = vol.All(vol.Coerce(float), vol.Range(min=0))

ADD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_QUANTITY, default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(ATTR_PACKAGE_SIZE): POSITIVE_FLOAT,
        vol.Optional(ATTR_BEST_BEFORE): cv.date,
        vol.Optional(ATTR_LOCATION, default=LOCATION_FREEZER): LOCATION,
    }
)
REMOVE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_QUANTITY): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(ATTR_LOCATION, default=LOCATION_FREEZER): LOCATION,
    }
)
SET_QUANTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_QUANTITY): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(ATTR_LOCATION, default=LOCATION_FREEZER): LOCATION,
    }
)
SET_UNITS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_UNITS): NON_NEGATIVE_FLOAT,
        vol.Optional(ATTR_LOCATION, default=LOCATION_FREEZER): LOCATION,
    }
)
USE_AMOUNT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_AMOUNT): POSITIVE_FLOAT,
        vol.Optional(ATTR_LOCATION, default=LOCATION_FREEZER): LOCATION,
    }
)
CLEAR_SCHEMA = vol.Schema({vol.Optional(ATTR_LOCATION): LOCATION})


def _sort_key(item: dict[str, Any]) -> tuple[bool, str]:
    """Sort by best-before date, oldest first, items without a date last."""
    best_before = item.get(ATTR_BEST_BEFORE)
    return (best_before is None, best_before or "")


class FreezerInventory:
    """Persistent freezer and fridge inventory.

    Every entry is one batch: a name, a number of packages, an optional package
    size, and an optional best-before date. The same name can have several
    batches with different dates.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass
        self.items: list[dict[str, Any]] = []
        self.revision = 0
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> None:
        """Load items from storage, migrating older data."""
        data = await self._store.async_load()
        self.items = data[ATTR_ITEMS] if data else []
        for item in self.items:
            item.setdefault(ATTR_ID, uuid.uuid4().hex[:8])
            item.setdefault(ATTR_PACKAGE_SIZE, None)
            item.setdefault(ATTR_REMAINING, None)
            item.setdefault(ATTR_BEST_BEFORE, None)
            item.setdefault(ATTR_LOCATION, LOCATION_FREEZER)
            item.pop("unit", None)

    async def async_save(self) -> None:
        """Write pending changes immediately."""
        await self._store.async_save({ATTR_ITEMS: self.items})

    @callback
    def _changed(self) -> None:
        self.revision += 1
        self._store.async_delay_save(lambda: {ATTR_ITEMS: self.items}, 1)
        self.hass.bus.async_fire(EVENT_UPDATED)

    def _matches(
        self, name: str, item_id: str | None = None, location: str = LOCATION_FREEZER
    ) -> list[dict[str, Any]]:
        """Return the entries for an id or name, oldest best-before first."""
        if item_id:
            return [i for i in self.items if i[ATTR_ID] == item_id]
        key = name.strip().casefold()
        return sorted(
            (
                i
                for i in self.items
                if i[ATTR_NAME].casefold() == key and i[ATTR_LOCATION] == location
            ),
            key=_sort_key,
        )

    def _find(
        self, name: str, item_id: str | None = None, location: str = LOCATION_FREEZER
    ) -> dict[str, Any] | None:
        matches = self._matches(name, item_id, location)
        return matches[0] if matches else None

    @callback
    def async_add(
        self,
        name: str,
        quantity: int = 1,
        best_before: str | None = None,
        package_size: float | None = None,
        location: str = LOCATION_FREEZER,
    ) -> None:
        """Add packages. A different best-before date creates a separate batch."""
        candidates = [
            i
            for i in self._matches(name, None, location)
            if package_size is None or i.get(ATTR_PACKAGE_SIZE) == package_size
        ]
        if best_before:
            candidates = [i for i in candidates if i.get(ATTR_BEST_BEFORE) == best_before]
        else:
            candidates.sort(key=lambda i: i.get(ATTR_BEST_BEFORE) is not None)
        item = candidates[0] if candidates else None

        if item is None:
            item = {
                ATTR_ID: uuid.uuid4().hex[:8],
                ATTR_NAME: name.strip(),
                ATTR_QUANTITY: 0,
                ATTR_PACKAGE_SIZE: package_size,
                ATTR_REMAINING: package_size,
                ATTR_DATE_ADDED: dt_util.now().date().isoformat(),
                ATTR_BEST_BEFORE: best_before,
                ATTR_LOCATION: location,
            }
            self.items.append(item)
        item[ATTR_QUANTITY] += quantity
        if item.get(ATTR_PACKAGE_SIZE) and item.get(ATTR_REMAINING) is None:
            item[ATTR_REMAINING] = item[ATTR_PACKAGE_SIZE]
        self._changed()

    @callback
    def async_remove(
        self,
        name: str,
        quantity: int | None = None,
        item_id: str | None = None,
        location: str = LOCATION_FREEZER,
    ) -> None:
        """Remove (part of) an entry."""
        item = self._find(name, item_id, location)
        if item is None:
            return
        if quantity is None or quantity >= item[ATTR_QUANTITY]:
            self.items.remove(item)
        else:
            item[ATTR_QUANTITY] -= quantity
        self._changed()

    @callback
    def async_set_quantity(
        self,
        name: str,
        quantity: int,
        item_id: str | None = None,
        location: str = LOCATION_FREEZER,
    ) -> None:
        """Set the number of packages (0 removes the entry)."""
        item = self._find(name, item_id, location)
        if item is None:
            return
        if quantity <= 0:
            self.items.remove(item)
        else:
            item[ATTR_QUANTITY] = quantity
        self._changed()

    @callback
    def async_set_units(
        self,
        name: str,
        units: float,
        item_id: str | None = None,
        location: str = LOCATION_FREEZER,
    ) -> None:
        """Set the total units; packages are recalculated (last one may be partial)."""
        item = self._find(name, item_id, location)
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
    def async_use_amount(
        self,
        name: str,
        amount: float,
        item_id: str | None = None,
        location: str = LOCATION_FREEZER,
    ) -> None:
        """Use part of the contents; opens the next package when one is used up.

        Without an id, the oldest best-before batch is used first.
        """
        changed = False
        for item in list(self._matches(name, item_id, location)):
            if amount <= 1e-9:
                break
            size = item.get(ATTR_PACKAGE_SIZE)
            if not size:
                continue
            changed = True
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
        if changed:
            self._changed()

    @callback
    def async_clear(self, location: str | None = None) -> None:
        """Remove all items, or only those in one location."""
        self.items = (
            [i for i in self.items if i[ATTR_LOCATION] != location] if location else []
        )
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
            best_before.isoformat() if best_before else None,
            call.data.get(ATTR_PACKAGE_SIZE),
            call.data[ATTR_LOCATION],
        )

    async def remove_item(call: ServiceCall) -> None:
        inventory.async_remove(
            call.data[ATTR_NAME],
            call.data.get(ATTR_QUANTITY),
            call.data.get(ATTR_ID),
            call.data[ATTR_LOCATION],
        )

    async def set_quantity(call: ServiceCall) -> None:
        inventory.async_set_quantity(
            call.data[ATTR_NAME],
            call.data[ATTR_QUANTITY],
            call.data.get(ATTR_ID),
            call.data[ATTR_LOCATION],
        )

    async def set_units(call: ServiceCall) -> None:
        inventory.async_set_units(
            call.data[ATTR_NAME],
            call.data[ATTR_UNITS],
            call.data.get(ATTR_ID),
            call.data[ATTR_LOCATION],
        )

    async def use_amount(call: ServiceCall) -> None:
        inventory.async_use_amount(
            call.data[ATTR_NAME],
            call.data[ATTR_AMOUNT],
            call.data.get(ATTR_ID),
            call.data[ATTR_LOCATION],
        )

    async def clear(call: ServiceCall) -> None:
        inventory.async_clear(call.data.get(ATTR_LOCATION))

    hass.services.async_register(DOMAIN, SERVICE_ADD_ITEM, add_item, ADD_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_ITEM, remove_item, REMOVE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_QUANTITY, set_quantity, SET_QUANTITY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_UNITS, set_units, SET_UNITS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_USE_AMOUNT, use_amount, USE_AMOUNT_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_CLEAR, clear, CLEAR_SCHEMA)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await _async_register_panel(hass)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)


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
        sidebar_title="Freezer & Fridge",
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
    inventory = hass.data.pop(DOMAIN)
    await inventory.async_save()
    return True
