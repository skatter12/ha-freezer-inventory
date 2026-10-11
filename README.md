# Freezer Inventory

[![Latest release](https://img.shields.io/github/v/release/skatter12/ha-freezer-inventory)](https://github.com/skatter12/ha-freezer-inventory/releases/latest)

**Current version: 0.5.0**

A Home Assistant integration that keeps track of what you have in your freezer.

## Installation (HACS)

1. In HACS, open the menu (top right) → **Custom repositories**.
2. Add `https://github.com/skatter12/ha-freezer-inventory` with category **Integration**.
3. Install **Freezer Inventory** and restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and search for "Freezer Inventory".

### Manual

Copy `custom_components/freezer_inventory` into your Home Assistant `config/custom_components/` folder and restart.

## Usage

After setup a **Freezer** entry appears in the sidebar. The panel needs Home Assistant 2024.7 or newer.

Each item has:

- **Quantity** – the number of packages.
- **Per package** (optional) – how many units are in each package.
- **Best before** (optional) – a date.

With 2 packages of 4, using 2 units gives `1 × 4 + 1 × 2 = 6`. The panel shows this breakdown and lets you edit both **Packages** and total **Units** (setting 5 units gives 2 packages: 4 + 1). Use the **Use** field to take units out of the open package; when it is empty the next package is opened.

### Adding to an existing item

Adding an item that already exists adds to it. If you give a **different best-before date**, it is stored as a separate batch under the same name, so each batch keeps its own date. Adding with the same date adds to the matching batch; adding without a date prefers a batch that has no date, otherwise the oldest one. Items expiring within 30 days are highlighted and expired ones are marked in red.

## Automations and services

- `sensor.freezer_items` shows the total number of packages; every batch is listed in its `items` attribute (with an `id`).
- Services (all take an optional batch `id`; without it the batch with the oldest best-before date is used):
  - `freezer_inventory.add_item` – `name`, optional `quantity`, `package_size`, `best_before`.
  - `freezer_inventory.remove_item` – `name`, optional `quantity` (omit to remove the whole batch).
  - `freezer_inventory.set_quantity` – `name`, `quantity` (0 removes the batch).
  - `freezer_inventory.set_units` – `name`, `units`. Sets the total units; packages are recalculated.
  - `freezer_inventory.use_amount` – `name`, `amount`. Uses units from the oldest batches first.
  - `freezer_inventory.clear` – empties the inventory.

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

- **0.5.0** – Removed the unit field. Adding an existing item with a new best-before date creates a separate batch. Existing items are migrated automatically.
- **0.4.0** – Panel shows packages and total units (e.g. 4 + 2 = 6) and both can be edited (`set_units`).
- **0.3.0** – Package size and partial use (`use_amount`).
- **0.2.2** – Panel updates immediately without a page refresh.
- **0.2.0** – Sidebar panel with full UI.
- **0.1.0** – Initial release.

## License

Apache 2.0
