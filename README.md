# Freezer Inventory

[![Latest release](https://img.shields.io/github/v/release/skatter12/ha-freezer-inventory)](https://github.com/skatter12/ha-freezer-inventory/releases/latest)

**Current version: 0.4.0**

A Home Assistant integration that keeps track of what you have in your freezer.

## Installation (HACS)

1. In HACS, open the menu (top right) → **Custom repositories**.
2. Add `https://github.com/skatter12/ha-freezer-inventory` with category **Integration**.
3. Install **Freezer Inventory** and restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and search for "Freezer Inventory".

### Manual

Copy `custom_components/freezer_inventory` into your Home Assistant `config/custom_components/` folder and restart.

## Usage

After setup a **Freezer** entry appears in the sidebar. The panel lets you add items (name, quantity, unit, best-before date), adjust quantities with +/−, delete items, search, and clear everything. Items expiring within 30 days are highlighted, and expired ones are marked in red. The panel needs Home Assistant 2024.7 or newer.

The same functionality is available to automations and scripts:

- `sensor.freezer_items` shows the total quantity; the full list is in its `items` attribute.
- Services:
  - `freezer_inventory.add_item` – `name`, optional `quantity`, `unit`, `best_before`. Adds to the quantity if the item already exists.
  - `freezer_inventory.remove_item` – `name`, optional `quantity` (omit to remove the whole item).
  - `freezer_inventory.set_quantity` – `name`, `quantity` (0 removes the item).
  - `freezer_inventory.set_units` – `name`, `units`. Sets the total units; packages are recalculated.
  - `freezer_inventory.use_amount` – `name`, `amount`. Uses part of a package without removing it (see below).
  - `freezer_inventory.clear` – empties the inventory.

### Partial use of a package

Set **Unit** (e.g. `pcs`) and **Per package** (e.g. `4`) when adding an item. With 2 packages of 4, using 2 gives `1 × 4 + 1 × 2 = 6 pcs`. The panel shows this breakdown and lets you edit both the number of **Packages** and the total **units**; the packages are recalculated automatically (e.g. setting 5 units gives 2 packages: 4 + 1). Use the "Use" field in the panel or the `use_amount` service to take out part of a package.

Example:

```yaml
service: freezer_inventory.add_item
data:
  name: Minced beef
  quantity: 2
  unit: bags
  best_before: "2027-03-01"
```

## Changelog

- **0.4.0** – Panel shows packages and total units (e.g. 4 + 2 = 6) and both can be edited (`set_units`).
- **0.3.0** – Package size and partial use (`use_amount`).
- **0.2.2** – Panel updates immediately without a page refresh.
- **0.2.0** – Sidebar panel with full UI.
- **0.1.0** – Initial release.

## License

Apache 2.0
