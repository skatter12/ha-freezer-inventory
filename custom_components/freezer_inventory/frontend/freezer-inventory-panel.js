const ENTITY_ID = "sensor.freezer_items";

class FreezerInventoryPanel extends HTMLElement {
  constructor() {
    super();
    this._filter = "";
    this._lastItems = null;
    this._built = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
    this._renderList();
  }

  set narrow(value) {
    this._narrow = value;
  }

  _build() {
    this._built = true;
    this.innerHTML = `
      <style>
        freezer-inventory-panel { display: block; }
        .fi-wrap { max-width: 800px; margin: 0 auto; padding: 16px;
          color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, sans-serif); }
        .fi-wrap h1 { margin: 0 0 16px; font-size: 24px; font-weight: 400; }
        .fi-card { background: var(--card-background-color, #fff); border-radius: 12px;
          padding: 16px; margin-bottom: 16px; box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.2)); }
        .fi-wrap form { display: grid; grid-template-columns: 2fr 1fr 1fr 1.5fr auto; gap: 8px; align-items: end; }
        .fi-wrap label { display: flex; flex-direction: column; font-size: 12px; gap: 4px; color: var(--secondary-text-color); }
        .fi-wrap input { padding: 8px; border-radius: 6px; font-size: 14px; box-sizing: border-box; width: 100%;
          border: 1px solid var(--divider-color, #ccc);
          background: var(--secondary-background-color, #fff); color: var(--primary-text-color); }
        .fi-wrap button { cursor: pointer; border: 0; border-radius: 6px; padding: 8px 12px; font-size: 14px;
          background: var(--primary-color); color: var(--text-primary-color, #fff); }
        .fi-wrap button.secondary { background: var(--secondary-background-color, #eee); color: var(--primary-text-color);
          border: 1px solid var(--divider-color, #ccc); }
        .fi-wrap button.danger { background: var(--error-color, #db4437); color: #fff; }
        .fi-toolbar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
        .fi-summary { color: var(--secondary-text-color); font-size: 13px; margin-bottom: 8px; }
        .fi-item { display: flex; align-items: center; gap: 8px; padding: 10px 0;
          border-bottom: 1px solid var(--divider-color, #ddd); }
        .fi-item:last-child { border-bottom: 0; }
        .fi-info { flex: 1; min-width: 0; }
        .fi-name { font-weight: 500; }
        .fi-meta { font-size: 12px; color: var(--secondary-text-color); }
        .fi-expired { color: var(--error-color, #db4437); font-weight: 500; }
        .fi-soon { color: var(--warning-color, #f4a100); font-weight: 500; }
        .fi-qty { min-width: 70px; text-align: center; font-size: 16px; }
        .fi-empty { text-align: center; color: var(--secondary-text-color); padding: 24px 0; }
        @media (max-width: 600px) { .fi-wrap form { grid-template-columns: 1fr 1fr; } }
      </style>
      <div class="fi-wrap">
        <h1>Freezer Inventory</h1>
        <div class="fi-card">
          <form id="add">
            <label>Name<input name="name" required placeholder="e.g. Minced beef" /></label>
            <label>Quantity<input name="quantity" type="number" min="1" value="1" required /></label>
            <label>Unit<input name="unit" placeholder="e.g. bags" /></label>
            <label>Best before<input name="best_before" type="date" /></label>
            <button type="submit">Add</button>
          </form>
        </div>
        <div class="fi-card">
          <div class="fi-toolbar">
            <input id="search" type="search" placeholder="Search items..." />
            <button id="clear" class="danger" type="button">Clear all</button>
          </div>
          <div class="fi-summary" id="summary"></div>
          <div id="list"></div>
        </div>
      </div>`;

    this.querySelector("#add").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const form = ev.target;
      const data = {
        name: form.name.value.trim(),
        quantity: parseInt(form.quantity.value, 10) || 1,
      };
      if (form.unit.value.trim()) data.unit = form.unit.value.trim();
      if (form.best_before.value) data.best_before = form.best_before.value;
      await this._hass.callService("freezer_inventory", "add_item", data);
      form.reset();
      form.quantity.value = 1;
      form.name.focus();
    });

    this.querySelector("#search").addEventListener("input", (ev) => {
      this._filter = ev.target.value.trim().toLowerCase();
      this._lastItems = null;
      this._renderList();
    });

    this.querySelector("#clear").addEventListener("click", () => {
      if (confirm("Remove everything from the freezer inventory?")) {
        this._hass.callService("freezer_inventory", "clear", {});
      }
    });

    this.querySelector("#list").addEventListener("click", (ev) => {
      const btn = ev.target.closest("button[data-action]");
      if (!btn) return;
      const name = btn.dataset.name;
      if (btn.dataset.action === "inc") {
        this._hass.callService("freezer_inventory", "add_item", { name, quantity: 1 });
      } else if (btn.dataset.action === "dec") {
        this._hass.callService("freezer_inventory", "remove_item", { name, quantity: 1 });
      } else if (btn.dataset.action === "del") {
        this._hass.callService("freezer_inventory", "remove_item", { name });
      }
    });
  }

  _esc(value) {
    const el = document.createElement("div");
    el.textContent = value ?? "";
    return el.innerHTML.replace(/"/g, "&quot;");
  }

  _expiry(bestBefore) {
    if (!bestBefore) return "";
    const days = Math.floor((new Date(bestBefore) - new Date().setHours(0, 0, 0, 0)) / 86400000);
    if (days < 0) return `<span class="fi-expired">Expired ${this._esc(bestBefore)}</span>`;
    if (days <= 30) return `<span class="fi-soon">Best before ${this._esc(bestBefore)} (${days}d)</span>`;
    return `Best before ${this._esc(bestBefore)}`;
  }

  _renderList() {
    const stateObj = this._hass.states[ENTITY_ID];
    const items = (stateObj && stateObj.attributes.items) || [];
    const key = JSON.stringify(items);
    if (key === this._lastItems) return;
    this._lastItems = key;

    const shown = items
      .filter((i) => i.name.toLowerCase().includes(this._filter))
      .sort((a, b) => a.name.localeCompare(b.name));

    const total = items.reduce((sum, i) => sum + i.quantity, 0);
    this.querySelector("#summary").textContent = stateObj
      ? `${items.length} items, ${total} total`
      : `Entity ${ENTITY_ID} not found. Is the integration set up?`;

    this.querySelector("#list").innerHTML = shown.length
      ? shown
          .map(
            (i) => `
        <div class="fi-item">
          <div class="fi-info">
            <div class="fi-name">${this._esc(i.name)}</div>
            <div class="fi-meta">Added ${this._esc(i.date_added)} ${this._expiry(i.best_before)}</div>
          </div>
          <button class="secondary" data-action="dec" data-name="${this._esc(i.name)}">−</button>
          <div class="fi-qty">${i.quantity}${i.unit ? " " + this._esc(i.unit) : ""}</div>
          <button class="secondary" data-action="inc" data-name="${this._esc(i.name)}">+</button>
          <button class="danger" data-action="del" data-name="${this._esc(i.name)}">Delete</button>
        </div>`
          )
          .join("")
      : `<div class="fi-empty">${items.length ? "No matches." : "The freezer is empty."}</div>`;
  }
}

customElements.define("freezer-inventory-panel", FreezerInventoryPanel);
