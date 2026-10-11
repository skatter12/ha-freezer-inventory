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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_AMOUNT,
    ATTR_BEST_BEFORE,
    ATTR_DATE_ADDED,
    ATTR_APPLIANCE,
    ATTR_ID,
    ATTR_ITEMS,
    ATTR_LOCATION,
    ATTR_NAME,
    ATTR_PACKAGE_SIZE,
    ATTR_QUANTITY,
    ATTR_REMAINING,
    ATTR_UNITS,
    CONF_APPLIANCES,
    CONF_SHOP_ON_ADD,
    CONF_SHOP_MIN,
    CONF_SHOP_ON_EMPTY,
    DOMAIN,
    EVENT_UPDATED,
    LOCATION_FREEZER,
    LOCATIONS,
    SERVICE_ADD_ITEM,
    SERVICE_ADD_TO_SHOPPING_LIST,
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
PANEL_VERSION = "1.2.0"
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
        vol.Optional(ATTR_APPLIANCE): cv.string,
    }
)
REMOVE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_QUANTITY): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(ATTR_LOCATION, default=LOCATION_FREEZER): LOCATION,
        vol.Optional(ATTR_APPLIANCE): cv.string,
    }
)
SET_QUANTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_QUANTITY): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(ATTR_LOCATION, default=LOCATION_FREEZER): LOCATION,
        vol.Optional(ATTR_APPLIANCE): cv.string,
    }
)
SET_UNITS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_UNITS): NON_NEGATIVE_FLOAT,
        vol.Optional(ATTR_LOCATION, default=LOCATION_FREEZER): LOCATION,
        vol.Optional(ATTR_APPLIANCE): cv.string,
    }
)
USE_AMOUNT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_AMOUNT): POSITIVE_FLOAT,
        vol.Optional(ATTR_LOCATION, default=LOCATION_FREEZER): LOCATION,
        vol.Optional(ATTR_APPLIANCE): cv.string,
    }
)
SHOPPING_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_LOCATION): LOCATION,
        vol.Optional(ATTR_APPLIANCE): cv.string,
    }
)
CLEAR_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_LOCATION): LOCATION, vol.Optional(ATTR_APPLIANCE): cv.string}
)


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
        self.appliances: list[dict[str, Any]] = []
        self.shop_on_empty = False
        self.shop_min: float = 0
        self.shop_on_add = False
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> None:
        """Load items from storage, migrating older data."""
        data = await self._store.async_load()
        self.items = data[ATTR_ITEMS] if data else []
        known = {a["id"] for a in self.appliances} | {None}
        for item in self.items:
            item.setdefault(ATTR_ID, uuid.uuid4().hex[:8])
            item.setdefault(ATTR_PACKAGE_SIZE, None)
            item.setdefault(ATTR_REMAINING, None)
            item.setdefault(ATTR_BEST_BEFORE, None)
            item.setdefault(ATTR_LOCATION, LOCATION_FREEZER)
            item.setdefault(ATTR_APPLIANCE, None)
            if item[ATTR_APPLIANCE] not in known:
                item[ATTR_APPLIANCE] = None
            item.pop("unit", None)

    async def async_save(self) -> None:
        """Write pending changes immediately."""
        await self._store.async_save({ATTR_ITEMS: self.items})

    async def _async_shop(self, service: str, name: str, strict: bool = False) -> None:
        """Call the shopping list integration."""
        try:
            await self.hass.services.async_call(
                "shopping_list", service, {"name": name}, blocking=True
            )
        except HomeAssistantError:
            if strict:
                raise

    def _shop(self, service: str, name: str) -> None:
        """Fire and forget a shopping list call if the integration is available."""
        if self.hass.services.has_service("shopping_list", service):
            self.hass.async_create_task(self._async_shop(service, name))

    def _stock(self, name: str, location: str, appliance: str | None) -> float:
        """Total units of an item across its batches."""
        total = 0.0
        for i in self._matches(name, None, location, appliance):
            size = i.get(ATTR_PACKAGE_SIZE)
            if size:
                remaining = i.get(ATTR_REMAINING)
                if remaining is None:
                    remaining = size
                total += (i[ATTR_QUANTITY] - 1) * size + remaining
            else:
                total += i[ATTR_QUANTITY]
        return total

    def _check_stock(
        self, name: str, location: str, appliance: str | None, before: float
    ) -> None:
        """Add to the shopping list when stock drops to the minimum or below."""
        if not self.shop_on_empty:
            return
        after = self._stock(name, location, appliance)
        if before > self.shop_min and after <= self.shop_min + 1e-9:
            self._shop("add_item", name)

    @callback
    def _changed(self) -> None:
        self.revision += 1
        self._store.async_delay_save(lambda: {ATTR_ITEMS: self.items}, 1)
        self.hass.bus.async_fire(EVENT_UPDATED)

    def _matches(
        self,
        name: str,
        item_id: str | None = None,
        location: str = LOCATION_FREEZER,
        appliance: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return the entries for an id or name, oldest best-before first."""
        if item_id:
            return [i for i in self.items if i[ATTR_ID] == item_id]
        key = name.strip().casefold()
        return sorted(
            (
                i
                for i in self.items
                if i[ATTR_NAME].casefold() == key
                and i[ATTR_LOCATION] == location
                and i.get(ATTR_APPLIANCE) == appliance
            ),
            key=_sort_key,
        )

    def _find(
        self,
        name: str,
        item_id: str | None = None,
        location: str = LOCATION_FREEZER,
        appliance: str | None = None,
    ) -> dict[str, Any] | None:
        matches = self._matches(name, item_id, location, appliance)
        return matches[0] if matches else None

    @callback
    def async_add(
        self,
        name: str,
        quantity: int = 1,
        best_before: str | None = None,
        package_size: float | None = None,
        location: str = LOCATION_FREEZER,
        appliance: str | None = None,
    ) -> None:
        """Add packages. A different best-before date creates a separate batch."""
        candidates = [
            i
            for i in self._matches(name, None, location, appliance)
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
                ATTR_APPLIANCE: appliance,
            }
            self.items.append(item)
        item[ATTR_QUANTITY] += quantity
        if item.get(ATTR_PACKAGE_SIZE) and item.get(ATTR_REMAINING) is None:
            item[ATTR_REMAINING] = item[ATTR_PACKAGE_SIZE]
        if self.shop_on_add:
            self._shop("complete_item", item[ATTR_NAME])
        self._changed()

    @callback
    def async_remove(
        self,
        name: str,
        quantity: int | None = None,
        item_id: str | None = None,
        location: str = LOCATION_FREEZER,
        appliance: str | None = None,
    ) -> None:
        """Remove (part of) an entry."""
        item = self._find(name, item_id, location, appliance)
        if item is None:
            return
        before = self._stock(name, location, appliance)
        if quantity is None or quantity >= item[ATTR_QUANTITY]:
            self.items.remove(item)
        else:
            item[ATTR_QUANTITY] -= quantity
        self._check_stock(item[ATTR_NAME], item[ATTR_LOCATION], item.get(ATTR_APPLIANCE), before)
        self._changed()

    @callback
    def async_set_quantity(
        self,
        name: str,
        quantity: int,
        item_id: str | None = None,
        location: str = LOCATION_FREEZER,
        appliance: str | None = None,
    ) -> None:
        """Set the number of packages (0 removes the entry)."""
        item = self._find(name, item_id, location, appliance)
        if item is None:
            return
        before = self._stock(name, location, appliance)
        if quantity <= 0:
            self.items.remove(item)
        else:
            item[ATTR_QUANTITY] = quantity
        self._check_stock(item[ATTR_NAME], item[ATTR_LOCATION], item.get(ATTR_APPLIANCE), before)
        self._changed()

    @callback
    def async_set_units(
        self,
        name: str,
        units: float,
        item_id: str | None = None,
        location: str = LOCATION_FREEZER,
        appliance: str | None = None,
    ) -> None:
        """Set the total units; packages are recalculated (last one may be partial)."""
        item = self._find(name, item_id, location, appliance)
        if item is None or not item.get(ATTR_PACKAGE_SIZE):
            return
        before = self._stock(name, location, appliance)
        size = item[ATTR_PACKAGE_SIZE]
        if units <= 1e-9:
            self.items.remove(item)
        else:
            packages = math.ceil(units / size - 1e-9)
            item[ATTR_QUANTITY] = packages
            item[ATTR_REMAINING] = round(units - (packages - 1) * size, 6)
        self._check_stock(item[ATTR_NAME], item[ATTR_LOCATION], item.get(ATTR_APPLIANCE), before)
        self._changed()

    @callback
    def async_use_amount(
        self,
        name: str,
        amount: float,
        item_id: str | None = None,
        location: str = LOCATION_FREEZER,
        appliance: str | None = None,
    ) -> None:
        """Use part of the contents; opens the next package when one is used up.

        Without an id, the oldest best-before batch is used first.
        """
        changed = False
        before = self._stock(name, location, appliance)
        for item in list(self._matches(name, item_id, location, appliance)):
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
            self._check_stock(name, location, appliance, before)
            self._changed()

    @callback
    def async_clear(
        self, location: str | None = None, appliance: str | None = None
    ) -> None:
        """Remove all items, or only those in one freezer/fridge."""
        if location is None and appliance is None:
            self.items = []
        else:
            self.items = [
                i
                for i in self.items
                if not (
                    i[ATTR_LOCATION] == location and i.get(ATTR_APPLIANCE) == appliance
                )
            ]
        self._changed()

    def resolve(self, data: dict[str, Any]) -> tuple[str | None, str | None]:
        """Return (kind, appliance id) for service data; appliance may be a name or id."""
        ref = data.get(ATTR_APPLIANCE)
        if ref:
            key = ref.strip().casefold()
            for appliance in self.appliances:
                if key in (appliance["id"].casefold(), appliance["name"].casefold()):
                    return appliance["kind"], appliance["id"]
            raise HomeAssistantError(f"Unknown freezer or fridge: {ref}")
        return data.get(ATTR_LOCATION), None

    @callback
    def async_remove_appliance(self, appliance_id: str) -> None:
        """Move the items of a deleted freezer/fridge back to the default one."""
        for item in self.items:
            if item.get(ATTR_APPLIANCE) == appliance_id:
                item[ATTR_APPLIANCE] = None
        self._changed()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Freezer Inventory from a config entry."""
    inventory = FreezerInventory(hass)
    conf = {**entry.data, **entry.options}
    inventory.appliances = list(conf.get(CONF_APPLIANCES) or [])
    inventory.shop_on_empty = bool(conf.get(CONF_SHOP_ON_EMPTY))
    inventory.shop_min = float(conf.get(CONF_SHOP_MIN) or 0)
    inventory.shop_on_add = bool(conf.get(CONF_SHOP_ON_ADD))
    await inventory.async_load()
    hass.data[DOMAIN] = inventory

    def _target(call: ServiceCall) -> tuple[str, str | None]:
        location, appliance = inventory.resolve(call.data)
        return location or LOCATION_FREEZER, appliance

    async def add_item(call: ServiceCall) -> None:
        best_before = call.data.get(ATTR_BEST_BEFORE)
        location, appliance = _target(call)
        inventory.async_add(
            call.data[ATTR_NAME],
            call.data[ATTR_QUANTITY],
            best_before.isoformat() if best_before else None,
            call.data.get(ATTR_PACKAGE_SIZE),
            location,
            appliance,
        )

    async def remove_item(call: ServiceCall) -> None:
        location, appliance = _target(call)
        inventory.async_remove(
            call.data[ATTR_NAME],
            call.data.get(ATTR_QUANTITY),
            call.data.get(ATTR_ID),
            location,
            appliance,
        )

    async def set_quantity(call: ServiceCall) -> None:
        location, appliance = _target(call)
        inventory.async_set_quantity(
            call.data[ATTR_NAME],
            call.data[ATTR_QUANTITY],
            call.data.get(ATTR_ID),
            location,
            appliance,
        )

    async def set_units(call: ServiceCall) -> None:
        location, appliance = _target(call)
        inventory.async_set_units(
            call.data[ATTR_NAME],
            call.data[ATTR_UNITS],
            call.data.get(ATTR_ID),
            location,
            appliance,
        )

    async def use_amount(call: ServiceCall) -> None:
        location, appliance = _target(call)
        inventory.async_use_amount(
            call.data[ATTR_NAME],
            call.data[ATTR_AMOUNT],
            call.data.get(ATTR_ID),
            location,
            appliance,
        )

    async def add_to_shopping_list(call: ServiceCall) -> None:
        if not hass.services.has_service("shopping_list", "add_item"):
            raise HomeAssistantError("The Shopping List integration is not set up")
        await inventory._async_shop("add_item", call.data[ATTR_NAME], strict=True)

    async def clear(call: ServiceCall) -> None:
        location, appliance = inventory.resolve(call.data)
        inventory.async_clear(location, appliance)

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
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_TO_SHOPPING_LIST, add_to_shopping_list, SHOPPING_SCHEMA
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
        SERVICE_ADD_TO_SHOPPING_LIST,
        SERVICE_CLEAR,
    ):
        hass.services.async_remove(DOMAIN, service)
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    inventory = hass.data.pop(DOMAIN)
    await inventory.async_save()
    return True
