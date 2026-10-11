"""Constants for the Freezer Inventory integration."""

DOMAIN = "freezer_inventory"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

SERVICE_ADD_ITEM = "add_item"
SERVICE_REMOVE_ITEM = "remove_item"
SERVICE_CLEAR = "clear"
SERVICE_SET_QUANTITY = "set_quantity"
SERVICE_USE_AMOUNT = "use_amount"

ATTR_NAME = "name"
ATTR_QUANTITY = "quantity"
ATTR_UNIT = "unit"
ATTR_PACKAGE_SIZE = "package_size"
ATTR_REMAINING = "remaining"
ATTR_AMOUNT = "amount"
ATTR_DATE_ADDED = "date_added"
ATTR_BEST_BEFORE = "best_before"
ATTR_ITEMS = "items"

EVENT_UPDATED = f"{DOMAIN}_updated"
