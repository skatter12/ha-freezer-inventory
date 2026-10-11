"""Config flow for Freezer Inventory."""
from homeassistant import config_entries

from .const import DOMAIN


class FreezerInventoryFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Freezer Inventory."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Freezer Inventory", data={})

        return self.async_show_form(step_id="user")
