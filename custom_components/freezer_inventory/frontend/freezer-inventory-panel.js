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
        .fi-wrap { max-width: 900px; margin: 0 auto; padding: 16px;
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
        .fi-hint { font-size: 12px; color: var(--secondary-text-color); margin-top: 8px; min-height: 16px; }
        .fi-toolbar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
        .fi-summary { color: var(--secondary-text-color); font-size: 13px; margin-bottom: 8px; }
        .fi-item { display: flex; align-items: center; gap: 8px; padding: 10px 0; flex-wrap: wrap;
          border-bottom: 1px solid var(--divider-color, #ddd); }
        .fi-item:last-child { border-bottom: 0; }
        .fi-info { flex: 1; min-width: 160px; }
        .fi-name { font-weight: 500; }
        .fi-meta { font-size: 12px; color: var(--secondary-text-color); }
        .fi-expired { color: var(--error-color, #db4437); font-weight: 500; }
        .fi-soon { color: var(--warning-color, #f4a100); font-weight: 500; }
        .fi-wrap input.fi-qty { width: 70px; text-align: center; font-size: 16px; }
        .fi-use { display: flex; gap: 6px; margin-top: 6px; }
        .fi-wrap .fi-use input { width: 90px; padding: 4px 6px; }
        .fi-wrap .fi-use button { padding: 4px 10px; }
        .fi-field { display: flex; flex-direction: column; font-size: 11px; align-items: center; }
        .fi-empty { text-align: center; color: var(--secondary-text-color); padding: 24px 0; }
        @media (max-width: 600px) { .fi-wrap form { grid-template-columns: 1fr 1fr; } }
      </style>
      <div class="fi-wrap">
        <h1>Freezer Inventory</h1>
        <div class="fi-card">
          <form id="add">
            <label>Name<input name="name" required list="fi-names" autocomplete="off" placeholder="e.g. Minced beef" /></label>
            <label>Quantity<input name="quantity" type="number" min="1" value="1" required /></label>
            <label>Per package<input name="package_size" type="number" min="0" step="any" placeholder="e.g. 4" /></label>
            <label>Best before<input name="best_before" type="date" /></label>
            <button type="submit">Add</button>
          </form>
          <datalist id="fi-names"></datalist>
          <div class="fi-hint" id="hint"></div>
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

    const form = this.querySelector("#add");
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const data = {
        name: form.name.value.trim(),
        quantity: parseInt(form.quantity.value, 10) || 1,
      };
      if (parseFloat(form.package_size.value) > 0) data.package_size = parseFloat(form.package_size.value);
      if (form.best_before.value) data.best_before = form.best_before.value;
      await this._call("add_item", data);
      form.reset();
      form.quantity.value = 1;
      this._updateHint();
      form.name.focus();
    });
    form.name.addEventListener("input", () => this._updateHint());

    this.querySelector("#search").addEventListener("input", (ev) => {
      this._filter = ev.target.value.trim().toLowerCase();
      this._lastItems = null;
      this._renderList();
    });

    this.querySelector("#clear").addEventListener("click", () => {
      if (confirm("Remove everything from the freezer inventory?")) {
        this._call("clear", {});
      }
    });

    this.querySelector("#list").addEventListener("click", (ev) => {
      const btn = ev.target.closest("button[data-action]");
      if (!btn) return;
      const target = { name: btn.dataset.name, id: btn.dataset.id };
      const qty = parseInt(btn.dataset.qty, 10) || 0;
      if (btn.dataset.action === "use") {
        const input = btn.parentElement.querySelector("input[data-action='use-amount']");
        const amount = parseFloat(input.value);
        if (amount > 0) this._call("use_amount", { ...target, amount });
      } else if (btn.dataset.action === "inc") {
        this._call("set_quantity", { ...target, quantity: qty + 1 });
      } else if (btn.dataset.action === "dec") {
        this._call("set_quantity", { ...target, quantity: Math.max(1, qty - 1) });
      } else if (btn.dataset.action === "del") {
        this._call("remove_item", target);
      }
    });

    this.querySelector("#list").addEventListener("change", (ev) => {
      const input = ev.target.closest("input[data-action]");
      if (!input) return;
      const target = { name: input.dataset.name, id: input.dataset.id };
      const value = parseFloat(input.value);
      if (Number.isNaN(value) || value < 0) {
        this._lastItems = null;
        this._renderList();
        return;
      }
      if (input.dataset.action === "set") {
        this._call("set_quantity", { ...target, quantity: Math.round(value) });
      } else if (input.dataset.action === "set-units") {
        this._call("set_units", { ...target, units: value });
      }
    });
  }

  async _call(service, data) {
    try {
      await this._hass.callService("freezer_inventory", service, data);
    } catch (err) {
      alert(`Freezer Inventory: ${err.message || err}`);
    }
    this._refreshSoon();
  }

  // Re-render shortly after a change, in case the state push is delayed.
  _refreshSoon() {
    for (const delay of [150, 600]) {
      setTimeout(() => {
        this._lastItems = null;
        this._renderList();
      }, delay);
    }
  }

  _items() {
    const stateObj = this._hass.states[ENTITY_ID];
    return (stateObj && stateObj.attributes.items) || [];
  }

  _updateHint() {
    const name = this.querySelector("#add").name.value.trim().toLowerCase();
    const existing = this._items().filter((i) => i.name.toLowerCase() === name);
    this.querySelector("#hint").textContent = existing.length
      ? `Already in the freezer: ${existing
          .map((i) => `${i.quantity} pkg${i.best_before ? ` (best before ${i.best_before})` : ""}`)
          .join(", ")}. Same date (or no date) adds to that batch; a new date creates a new batch.`
      : "";
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

  _totalUnits(i) {
    const remaining = i.remaining ?? i.package_size;
    return Math.round(((i.quantity - 1) * i.package_size + remaining) * 1e6) / 1e6;
  }

  _breakdown(i) {
    const remaining = i.remaining ?? i.package_size;
    const full = i.quantity - 1;
    const parts = [];
    if (full > 0) parts.push(`${full} × ${i.package_size}`);
    parts.push(`1 × ${remaining}`);
    return `${parts.join(" + ")} = ${this._totalUnits(i)}`;
  }

  _renderList() {
    const stateObj = this._hass.states[ENTITY_ID];
    const items = this._items();
    const key = JSON.stringify(items);
    if (key === this._lastItems) return;
    this._lastItems = key;

    const names = [...new Set(items.map((i) => i.name))];
    this.querySelector("#fi-names").innerHTML = names.map((n) => `<option value="${this._esc(n)}"></option>`).join("");
    this._updateHint();

    const shown = items
      .filter((i) => i.name.toLowerCase().includes(this._filter))
      .sort(
        (a, b) =>
          a.name.localeCompare(b.name) ||
          (a.best_before || "9999").localeCompare(b.best_before || "9999")
      );

    this.querySelector("#summary").textContent = stateObj
      ? `${names.length} items in ${items.length} batches`
      : `Entity ${ENTITY_ID} not found. Is the integration set up?`;

    this.querySelector("#list").innerHTML = shown.length
      ? shown
          .map((i) => {
            const ref = `data-name="${this._esc(i.name)}" data-id="${this._esc(i.id)}"`;
            return `
        <div class="fi-item">
          <div class="fi-info">
            <div class="fi-name">${this._esc(i.name)}</div>
            <div class="fi-meta">Added ${this._esc(i.date_added)} ${this._expiry(i.best_before)}</div>
            ${
              i.package_size
                ? `<div class="fi-meta">${this._breakdown(i)}</div>
                   <div class="fi-use">
                     <input type="number" min="0" step="any" placeholder="Used" data-action="use-amount" />
                     <button class="secondary" data-action="use" ${ref}>Use</button>
                   </div>`
                : ""
            }
          </div>
          <button class="secondary" data-action="dec" ${ref} data-qty="${i.quantity}">−</button>
          <label class="fi-field">Packages
            <input class="fi-qty" type="number" min="0" value="${i.quantity}" data-action="set" ${ref} />
          </label>
          <button class="secondary" data-action="inc" ${ref} data-qty="${i.quantity}">+</button>
          ${
            i.package_size
              ? `<label class="fi-field">Units
                   <input class="fi-qty" type="number" min="0" step="any" value="${this._totalUnits(i)}" data-action="set-units" ${ref} />
                 </label>`
              : ""
          }
          <button class="danger" data-action="del" ${ref}>Delete</button>
        </div>`;
          })
          .join("")
      : `<div class="fi-empty">${items.length ? "No matches." : "The freezer is empty."}</div>`;
  }
}

customElements.define("freezer-inventory-panel", FreezerInventoryPanel);
