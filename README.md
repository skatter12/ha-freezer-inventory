# Freezer Inventory

A Home Assistant integration that keeps track of what you have in your freezer.

## Installation (HACS)

1. In HACS, open the menu (top right) → **Custom repositories**.
2. Add `https://github.com/skatter12/ha-freezer-inventory` with category **Integration**.
3. Install **Freezer Inventory** and restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and search for "Freezer Inventory".

### Manual

Copy `custom_components/freezer_inventory` into your Home Assistant `config/custom_components/` folder and restart.

## Usage

- `sensor.freezer_items` shows the total quantity; the full list is in its `items` attribute.
- Services:
  - `freezer_inventory.add_item` – `name`, optional `quantity`, `unit`, `best_before`. Adds to the quantity if the item already exists.
  - `freezer_inventory.remove_item` – `name`, optional `quantity` (omit to remove the whole item).
  - `freezer_inventory.clear` – empties the inventory.

Example:

```yaml
service: freezer_inventory.add_item
data:
  name: Minced beef
  quantity: 2
  unit: bags
  best_before: "2027-03-01"
```

## License

Apache 2.0
