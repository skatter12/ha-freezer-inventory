# Freezer Inventory

[![Latest release](https://img.shields.io/github/v/release/skatter12/ha-freezer-inventory)](https://github.com/skatter12/ha-freezer-inventory/releases/latest)

**Current version: 1.7.1**

A Home Assistant integration that keeps track of what you have in your freezer.

## Installation (HACS)

1. In HACS, open the menu (top right) - **Custom repositories**.
2. Add `https://github.com/skatter12/ha-freezer-inventory` with category **Integration**.
3. Install **Freezer Inventory** and restart Home Assistant.
4. Go to **Settings - Devices & Services - Add Integration** and search for "Freezer Inventory".

### Manual

Copy `custom_components/freezer_inventory` into your Home Assistant `config/custom_components/` folder and restart.

## Usage

After setup a **Freezer** entry appears in the sidebar. The panel needs Home Assistant 2024.7 or newer.

Each item has:

- **Units** - how many you have (packages, cartons, trays...).
- **Per package** (optional) - how many units are in each package.
- **Best before** (optional) - a date.

With 2 packages of 4, using 2 units gives `1 -- 4 + 1 -- 2 = 6`. The panel shows this breakdown and lets you edit both **Units** and **Total** (setting 5 units gives 2 packages: 4 + 1). Use the **Use** field to take units out of the open package; when it is empty the next package is opened.

### Adding to an existing item

Adding an item that already exists adds to it. If you give a **different best-before date**, it is stored as a separate batch under the same name, so each batch keeps its own date. Adding with the same date adds to the matching batch; adding without a date prefers a batch that has no date, otherwise the oldest one. Items expiring within 30 days are highlighted and expired ones are marked in red.

## Multiple freezers and fridges

Under **Settings - Devices & Services - Freezer Inventory - Configure** you can add extra freezers and fridges with a name (and an optional temperature entity), rename them, and remove them again. Each one gets its own tab and its own sensor (`sensor.freezer_inventory_<id>`).

When adding an item, pick the freezer or fridge in the **Place** field (shown once you have more than the defaults). Leave it as is to use the current tab. Removing a freezer or fridge moves its items back to the default Freezer or Fridge.

Services accept an optional `appliance` (the name of an extra freezer or fridge), which overrides `location`.

## Temperature

When adding the integration you can pick a temperature entity (sensor or input_number) for the freezer and for the fridge. Change them later under **Settings - Devices & Services - Freezer Inventory - Configure**. The current temperature is shown in the tabs and under them.

## Shopping list

Works with the built-in Home Assistant **Shopping List** integration.

- Each item has a **Shopping list** button that adds it to the list.
- Under **Configure** you can enable: mark an item as bought on the shopping list when you add stock.
- Each item has a **Min stock** button. Set a number and choose **Units** (count) or **Total** (units x per package); when stock falls to that level the item is added to the shopping list. Leave it empty for no automatic adding. Service `freezer_inventory.set_min_stock`.
- Service `freezer_inventory.add_to_shopping_list` (`name`) for automations.

## Automations and services

- `sensor.freezer_items` and `sensor.fridge_items` show the total number of packages; every batch is listed in their `items` attribute (with an `id`).
- All services take an optional `location` (`freezer` or `fridge`, default `freezer`). `clear` without a location clears both.
- Services (all take an optional batch `id`; without it the batch with the oldest best-before date is used):
  - `freezer_inventory.add_item` - `name`, optional `quantity`, `package_size`, `best_before`.
  - `freezer_inventory.remove_item` - `name`, optional `quantity` (omit to remove the whole batch).
  - `freezer_inventory.set_quantity` - `name`, `quantity` (0 removes the batch).
  - `freezer_inventory.set_units` - `name`, `units`. Sets the total units; packages are recalculated.
  - `freezer_inventory.use_amount` - `name`, `amount`. Uses units from the oldest batches first.
  - `freezer_inventory.clear` - empties the inventory.

Example:

```yaml
service: freezer_inventory.add_item
data:
  name: Minced beef
  quantity: 2
  package_size: 4
  best_before: "2027-03-01"
```

## Changelog

- **1.7.1** - Panel labels: "Packages" is now "Units", and the old total "Units" is now "Total".
- **1.7.0** - Packages of different sizes with the same best-before date share one batch (e.g. 1 x 10 + 1 x 6 = 16). "Quantity" renamed to "Packages". Existing data is migrated automatically.
- **1.6.1** - Changing a batch date to one that already exists merges the two batches (same package size).
- **1.6.0** - Adding without a date creates/uses a separate "No date" batch; click a date (or "No date") to change it. New service `set_best_before`.
- **1.5.0** - Date format moved from the panel to Configure - Settings (applies to everyone).
- **1.4.0** - Automatic shopping list adding is now controlled only per item (global minimum setting removed).
- **1.3.3** - Min stock can be set to Off per item, overriding the default.
- **1.3.2** - Min stock is now a collapsible row, opened with a button on the item.
- **1.3.1** - Using more units than one batch holds continues into the next batch (oldest best-before first).
- **1.3.0** - Minimum stock per item, counted in quantity or units.
- **1.2.0** - Fixes a missing constant in 1.1.0 that stopped the integration from loading. Automatic shopping list can be switched on/off, with a minimum stock level that triggers adding the item.
- **1.1.0** - Add several named freezers and fridges (add, rename, remove under Configure), choose one when adding items.
- **1.0.0** - First stable release.

## License

Apache 2.0
