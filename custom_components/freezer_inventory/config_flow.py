"""Config flow for Freezer Inventory."""
from __future__ import annotations

from typing import Any
import uuid

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_APPLIANCES,
    CONF_FREEZER_TEMP,
    CONF_FRIDGE_TEMP,
    CONF_DATE_FORMAT,
    CONF_SHOP_ON_ADD,
    DATE_FORMATS,
    DEFAULT_DATE_FORMAT,
    DOMAIN,
    LOCATION_FREEZER,
    LOCATION_FRIDGE,
)

CONF_KIND = "kind"
CONF_NAME = "name"
CONF_TEMP = "temperature_entity"
CONF_UNIT = "unit"

TEMP_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["sensor", "input_number"])
)
KIND_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value=LOCATION_FREEZER, label="Freezer"),
            selector.SelectOptionDict(value=LOCATION_FRIDGE, label="Fridge"),
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)


def _optional_entity(key: str, suggested: str | None) -> tuple[Any, Any]:
    """Optional entity field with the current value pre-filled."""
    return (
        vol.Optional(
            key, description={"suggested_value": suggested} if suggested else None
        ),
        TEMP_SELECTOR,
    )


def _settings_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Schema for the default freezer/fridge temperatures and shopping list."""
    fields: dict[Any, Any] = {}
    for key in (CONF_FREEZER_TEMP, CONF_FRIDGE_TEMP):
        marker, sel = _optional_entity(key, defaults.get(key))
        fields[marker] = sel
    fields[
        vol.Optional(
            CONF_DATE_FORMAT,
            default=defaults.get(CONF_DATE_FORMAT) or DEFAULT_DATE_FORMAT,
        )
    ] = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=DATE_FORMATS, mode=selector.SelectSelectorMode.DROPDOWN
        )
    )
    fields[vol.Optional(CONF_SHOP_ON_ADD, default=bool(defaults.get(CONF_SHOP_ON_ADD, False)))] = bool
    return vol.Schema(fields)


class FreezerInventoryFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Freezer Inventory."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return FreezerInventoryOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Fridge/Freezer Inventory", data=user_input)

        return self.async_show_form(step_id="user", data_schema=_settings_schema({}))


class FreezerInventoryOptionsFlow(config_entries.OptionsFlow):
    """Settings, plus adding, editing and removing extra freezers and fridges."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self._entry = config_entry
        self._edit_id: str | None = None

    @property
    def _current(self) -> dict[str, Any]:
        return {**self._entry.data, **self._entry.options}

    @property
    def _appliances(self) -> list[dict[str, Any]]:
        return [dict(a) for a in self._current.get(CONF_APPLIANCES) or []]

    def _save(self, appliances: list[dict[str, Any]], **changes: Any):
        """Store the options; keys set to None are treated as cleared."""
        data = {**self._current, CONF_APPLIANCES: appliances, **changes}
        return self.async_create_entry(title="", data=data)

    def _unit_options(self) -> list[selector.SelectOptionDict]:
        return [
            selector.SelectOptionDict(
                value=a["id"], label=f"{a['name']} ({a['kind']})"
            )
            for a in self._appliances
        ]

    def _name_taken(self, name: str, ignore_id: str | None = None) -> bool:
        key = name.strip().casefold()
        if key in ("freezer", "fridge"):
            return True
        return any(
            a["name"].casefold() == key and a["id"] != ignore_id
            for a in self._appliances
        )

    async def async_step_init(self, user_input=None):
        """Show the menu."""
        options = ["settings", "add_unit"]
        if self._appliances:
            options += ["edit_pick", "remove_unit"]
        return self.async_show_menu(step_id="init", menu_options=options)

    async def async_step_settings(self, user_input=None):
        """Default freezer/fridge temperatures and shopping list options."""
        if user_input is not None:
            changes = {
                key: user_input.get(key) for key in (CONF_FREEZER_TEMP, CONF_FRIDGE_TEMP)
            }
            changes[CONF_DATE_FORMAT] = user_input.get(CONF_DATE_FORMAT, DEFAULT_DATE_FORMAT)
            changes[CONF_SHOP_ON_ADD] = user_input.get(CONF_SHOP_ON_ADD, False)
            return self._save(self._appliances, **changes)
        return self.async_show_form(
            step_id="settings", data_schema=_settings_schema(self._current)
        )

    async def async_step_add_unit(self, user_input=None):
        """Add another freezer or fridge."""
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            elif self._name_taken(name):
                errors[CONF_NAME] = "name_exists"
            else:
                appliances = self._appliances
                appliances.append(
                    {
                        "id": uuid.uuid4().hex[:6],
                        "kind": user_input[CONF_KIND],
                        "name": name,
                        "temperature_entity": user_input.get(CONF_TEMP),
                    }
                )
                return self._save(appliances)

        marker, sel = _optional_entity(CONF_TEMP, (user_input or {}).get(CONF_TEMP))
        schema = vol.Schema(
            {
                vol.Required(CONF_KIND, default=LOCATION_FREEZER): KIND_SELECTOR,
                vol.Required(CONF_NAME): str,
                marker: sel,
            }
        )
        return self.async_show_form(
            step_id="add_unit", data_schema=schema, errors=errors
        )

    async def async_step_edit_pick(self, user_input=None):
        """Choose which freezer/fridge to edit."""
        if user_input is not None:
            self._edit_id = user_input[CONF_UNIT]
            return await self.async_step_edit_unit()
        schema = vol.Schema(
            {
                vol.Required(CONF_UNIT): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._unit_options(),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="edit_pick", data_schema=schema)

    async def async_step_edit_unit(self, user_input=None):
        """Rename a freezer/fridge or change its temperature entity."""
        appliances = self._appliances
        target = next((a for a in appliances if a["id"] == self._edit_id), None)
        if target is None:
            return await self.async_step_init()
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            elif self._name_taken(name, target["id"]):
                errors[CONF_NAME] = "name_exists"
            else:
                target["name"] = name
                target["temperature_entity"] = user_input.get(CONF_TEMP)
                return self._save(appliances)

        marker, sel = _optional_entity(CONF_TEMP, target.get("temperature_entity"))
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=target["name"]): str,
                marker: sel,
            }
        )
        return self.async_show_form(
            step_id="edit_unit", data_schema=schema, errors=errors
        )

    async def async_step_remove_unit(self, user_input=None):
        """Remove a freezer/fridge; its items move to the default one."""
        if user_input is not None:
            unit_id = user_input[CONF_UNIT]
            inventory = self.hass.data.get(DOMAIN)
            if inventory is not None:
                inventory.async_remove_appliance(unit_id)
            return self._save([a for a in self._appliances if a["id"] != unit_id])
        schema = vol.Schema(
            {
                vol.Required(CONF_UNIT): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._unit_options(),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="remove_unit", data_schema=schema)
