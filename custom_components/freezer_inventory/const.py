"""Constants for the Freezer Inventory integration."""

DOMAIN = "freezer_inventory"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

SERVICE_ADD_ITEM = "add_item"
SERVICE_REMOVE_ITEM = "remove_item"
SERVICE_SET_QUANTITY = "set_quantity"
SERVICE_SET_UNITS = "set_units"
SERVICE_USE_AMOUNT = "use_amount"
SERVICE_CLEAR = "clear"

ATTR_ID = "id"
ATTR_NAME = "name"
ATTR_QUANTITY = "quantity"
ATTR_PACKAGE_SIZE = "package_size"
ATTR_REMAINING = "remaining"
ATTR_AMOUNT = "amount"
ATTR_UNITS = "units"
ATTR_DATE_ADDED = "date_added"
ATTR_BEST_BEFORE = "best_before"
ATTR_ITEMS = "items"
ATTR_LOCATION = "location"

LOCATION_FREEZER = "freezer"
LOCATION_FRIDGE = "fridge"
LOCATIONS = [LOCATION_FREEZER, LOCATION_FRIDGE]

EVENT_UPDATED = f"{DOMAIN}_updated"
