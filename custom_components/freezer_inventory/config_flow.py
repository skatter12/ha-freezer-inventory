"""Config flow for Freezer Inventory."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_FREEZER_TEMP, CONF_FRIDGE_TEMP, DOMAIN

TEMP_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["sensor", "input_number"])
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the form schema with the current values pre-filled."""
    fields: dict[Any, Any] = {}
    for key in (CONF_FREEZER_TEMP, CONF_FRIDGE_TEMP):
        suggested = defaults.get(key)
        fields[
            vol.Optional(
                key, description={"suggested_value": suggested} if suggested else None
            )
        ] = TEMP_SELECTOR
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
            return self.async_create_entry(title="Freezer Inventory", data=user_input)

        return self.async_show_form(step_id="user", data_schema=_schema({}))


class FreezerInventoryOptionsFlow(config_entries.OptionsFlow):
    """Change the temperature entities."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self._entry.data, **self._entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(current))
