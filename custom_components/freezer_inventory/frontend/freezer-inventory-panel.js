const DEFAULT_TABS = [
  { key: "freezer", kind: "freezer", label: "Freezer", entity: "sensor.freezer_items" },
  { key: "fridge", kind: "fridge", label: "Fridge", entity: "sensor.fridge_items" },
];

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
    this._open = this._open || new Set();
    this._loc = localStorage.getItem("freezer_inventory_location") || "freezer";
    const formats = ["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY", "DD.MM.YYYY", "DD-MM-YYYY", "YYYY/MM/DD", "YYYY.MM.DD", "D MMM YYYY", "MMM D, YYYY"];
    this._dateFormat = localStorage.getItem("freezer_inventory_date_format") || "YYYY-MM-DD";
    if (!formats.includes(this._dateFormat)) this._dateFormat = "YYYY-MM-DD";
    this.innerHTML = `
      <style>
        freezer-inventory-panel { display: block; }
        .fi-wrap { max-width: 900px; margin: 0 auto; padding: 16px;
          color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, sans-serif); }
        .fi-wrap h1 { margin: 0 0 16px; font-size: 24px; font-weight: 400; }
        .fi-card { background: var(--card-background-color, #fff); border-radius: 12px;
          padding: 16px; margin-bottom: 16px; box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.2)); }
        .fi-wrap form { display: grid; grid-template-columns: 1.2fr 2fr 1fr 1fr 1.5fr auto; gap: 8px; align-items: end; }
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
        .fi-gtitle { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
        .fi-gtitle .fi-meta { flex: 1; }
        .fi-addrow { display: flex; gap: 6px; flex-wrap: wrap; margin: 6px 0; }
        .fi-addrow input { width: 130px; }
        .fi-tabs { display: flex; gap: 8px; margin-bottom: 16px; }
        .fi-wrap .fi-tabs button { flex: 1; padding: 10px; font-size: 16px; border-radius: 10px;
          background: var(--secondary-background-color, #eee); color: var(--primary-text-color);
          border: 1px solid var(--divider-color, #ccc); }
        .fi-wrap .fi-tabs button.active { background: var(--primary-color); color: var(--text-primary-color, #fff); }
        .fi-temp { font-size: 15px; margin: -6px 0 14px; color: var(--secondary-text-color); }
        .fi-temp b { font-size: 22px; color: var(--primary-text-color); }
        .fi-box { border: 1px solid var(--divider-color, #ccc); border-radius: 16px; padding: 12px 16px;
          margin-bottom: 14px; background: var(--secondary-background-color, #f7f7f7); }
        .fi-box .fi-gtitle { margin-top: 0; font-size: 17px; }
        .fi-box .fi-item:last-child { border-bottom: 0; }
        .fi-date { display: inline-block; font-size: 15px; font-weight: 600; padding: 2px 10px; border-radius: 10px;
          background: var(--primary-color); color: var(--text-primary-color, #fff); }
        .fi-date.fi-d-soon { background: var(--warning-color, #f4a100); }
        .fi-date.fi-d-expired { background: var(--error-color, #db4437); }
        .fi-name { font-size: 11px; text-transform: uppercase; color: var(--secondary-text-color); }
        .fi-wrap select { padding: 8px; border-radius: 6px; border: 1px solid var(--divider-color, #ccc);
          background: var(--secondary-background-color, #fff); color: var(--primary-text-color); }
        .fi-empty { text-align: center; color: var(--secondary-text-color); padding: 24px 0; }
        @media (max-width: 600px) { .fi-wrap form { grid-template-columns: 1fr 1fr; } }
      </style>
      <div class="fi-wrap">
        <h1>Inventory</h1>
        <div class="fi-tabs" id="tabs"></div>
        <div class="fi-temp" id="temp"></div>
        <div class="fi-card">
          <form id="add">
            <label style="display:none">Place<select name="place" id="place"></select></label>
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
            <select id="datefmt" title="Date format"></select>
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
      const target = form.place.value || this._loc;
      await this._call("add_item", data, target);
      if (target !== this._loc) {
        this._loc = target;
        localStorage.setItem("freezer_inventory_location", target);
        this._open = new Set();
      }
      this._lastItems = null;
      form.reset();
      form.place.value = this._loc;
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

    this.querySelector("#tabs").addEventListener("click", (ev) => {
      const btn = ev.target.closest("button[data-loc]");
      if (!btn || btn.dataset.loc === this._loc) return;
      this._loc = btn.dataset.loc;
      localStorage.setItem("freezer_inventory_location", this._loc);
      this._open = new Set();
      this._lastItems = null;
      this._renderList();
    });

    const fmtSel = this.querySelector("#datefmt");
    fmtSel.innerHTML = formats
      .map((f) => `<option value="${f}"${f === this._dateFormat ? " selected" : ""}>${f}</option>`)
      .join("");
    fmtSel.addEventListener("change", () => {
      this._dateFormat = fmtSel.value;
      localStorage.setItem("freezer_inventory_date_format", this._dateFormat);
      this._lastItems = null;
      this._renderList();
    });

    this.querySelector("#clear").addEventListener("click", () => {
      if (confirm(`Remove everything from ${this._tab().label}?`)) {
        this._call("clear", {});
      }
    });

    this.querySelector("#list").addEventListener("click", (ev) => {
      const btn = ev.target.closest("button[data-action]");
      if (!btn) return;
      if (btn.dataset.action === "toggle-add") {
        const nm = btn.dataset.name;
        if (this._open.has(nm)) this._open.delete(nm);
        else this._open.add(nm);
        this._lastItems = null;
        this._renderList();
        return;
      }
      if (btn.dataset.action === "shop") {
        this._call("add_to_shopping_list", { name: btn.dataset.name }).then((ok) => ok &&
          this._toast(`${btn.dataset.name} added to the shopping list`)
        );
        return;
      }
      if (btn.dataset.action === "add-batch") {
        const row = btn.closest(".fi-addrow");
        const val = (f) => row.querySelector(`[data-f=${f}]`).value;
        const data = { name: btn.dataset.name, quantity: parseInt(val("quantity"), 10) || 1 };
        if (parseFloat(val("package_size")) > 0) data.package_size = parseFloat(val("package_size"));
        if (val("best_before")) data.best_before = val("best_before");
        this._open.delete(btn.dataset.name);
        this._call("add_item", data);
        return;
      }
      const target = { name: btn.dataset.name, id: btn.dataset.id };
      const qty = parseInt(btn.dataset.qty, 10) || 0;
      if (btn.dataset.action === "use") {
        const input = btn.parentElement.querySelector("input[data-action='use-amount']");
        const amount = parseFloat(input.value);
        if (amount > 0) this._call("use_amount", { ...target, amount });
      } else if (btn.dataset.action === "inc") {
        this._call("set_quantity", { ...target, quantity: qty + 1 });
      } else if (btn.dataset.action === "dec") {
        if (qty <= 1) {
          if (confirm("This is the last one in this batch. Remove the batch?")) this._call("remove_item", target);
        } else {
          this._call("set_quantity", { ...target, quantity: qty - 1 });
        }
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

  async _call(service, data, tabKey = this._loc) {
    let ok = true;
    const tab = this._tab(tabKey);
    try {
      await this._hass.callService("freezer_inventory", service, {
        ...data,
        location: tab.kind,
        ...(tab.appliance ? { appliance: tab.appliance } : {}),
      });
    } catch (err) {
      ok = false;
      alert(`Freezer Inventory: ${err.message || err}`);
    }
    this._refreshSoon();
    return ok;
  }

  _toast(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true }));
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

  _tabs() {
    const base = this._hass.states["sensor.freezer_items"];
    const extra = ((base && base.attributes.appliances) || []).map((a) => ({
      key: a.id,
      kind: a.kind,
      label: a.name,
      entity: `sensor.freezer_inventory_${a.id}`,
      appliance: a.id,
    }));
    return [...DEFAULT_TABS, ...extra];
  }

  _tab(key = this._loc) {
    const tabs = this._tabs();
    return tabs.find((t) => t.key === key) || tabs[0];
  }

  _temp(key) {
    const sensor = this._hass.states[this._tab(key).entity];
    const id = sensor && sensor.attributes.temperature_entity;
    if (!id) return null;
    const st = this._hass.states[id];
    if (!st) return { text: "unavailable" };
    const v = parseFloat(st.state);
    if (Number.isNaN(v)) return { text: st.state };
    const unit = st.attributes.unit_of_measurement || "";
    return { text: `${Math.round(v * 10) / 10} ${unit}`.trim() };
  }

  _items() {
    const stateObj = this._hass.states[this._tab().entity];
    return (stateObj && stateObj.attributes.items) || [];
  }

  _updateHint() {
    const name = this.querySelector("#add").name.value.trim().toLowerCase();
    const existing = this._items().filter((i) => i.name.toLowerCase() === name);
    this.querySelector("#hint").textContent = existing.length
      ? `Already in the freezer: ${existing
          .map((i) => `${i.quantity} pkg${i.best_before ? ` (best before ${this._fmtDate(i.best_before)})` : ""}`)
          .join(", ")}. Same date (or no date) adds to that batch; a new date creates a new batch.`
      : "";
  }

  _esc(value) {
    const el = document.createElement("div");
    el.textContent = value ?? "";
    return el.innerHTML.replace(/"/g, "&quot;");
  }

  _fmtDate(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    if (!m) return iso || "";
    const [, y, mo, d] = m;
    const mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][+mo - 1];
    switch (this._dateFormat) {
      case "DD/MM/YYYY": return `${d}/${mo}/${y}`;
      case "MM/DD/YYYY": return `${mo}/${d}/${y}`;
      case "DD.MM.YYYY": return `${d}.${mo}.${y}`;
      case "DD-MM-YYYY": return `${d}-${mo}-${y}`;
      case "YYYY/MM/DD": return `${y}/${mo}/${d}`;
      case "YYYY.MM.DD": return `${y}.${mo}.${d}`;
      case "D MMM YYYY": return `${+d} ${mon} ${y}`;
      case "MMM D, YYYY": return `${mon} ${+d}, ${y}`;
      default: return iso;
    }
  }

  _expiry(bestBefore) {
    if (!bestBefore) return `<span class="fi-date">No date</span>`;
    const days = Math.floor((new Date(bestBefore) - new Date().setHours(0, 0, 0, 0)) / 86400000);
    const f = this._esc(this._fmtDate(bestBefore));
    if (days < 0) return `<span class="fi-date fi-d-expired">Expired ${f}</span>`;
    if (days <= 30) return `<span class="fi-date fi-d-soon">Best before ${f} (${days}d)</span>`;
    return `<span class="fi-date">Best before ${f}</span>`;
  }

  _totalUnits(i) {
    const remaining = i.remaining ?? i.package_size;
    return Math.round(((i.quantity - 1) * i.package_size + remaining) * 1e6) / 1e6;
  }

  _breakdown(i) {
    const remaining = i.remaining ?? i.package_size;
    const full = i.quantity - 1;
    const parts = [];
    if (full > 0) parts.push(`${full} x ${i.package_size}`);
    parts.push(`1 x ${remaining}`);
    return `${parts.join(" + ")} = ${this._totalUnits(i)}`;
  }

  _groupHead(name, items) {
    const batches = items.filter((b) => b.name === name);
    const pkgs = batches.reduce((s, b) => s + b.quantity, 0);
    const withSize = batches.filter((b) => b.package_size);
    const units = withSize.reduce((s, b) => s + this._totalUnits(b), 0);
    const dates = new Set(batches.map((b) => b.best_before || "")).size;
    const n = this._esc(name);
    const open = this._open.has(name);
    return `<div class="fi-group">
      <div class="fi-gtitle"><b>${n}</b>
        <span class="fi-meta">Total: ${pkgs} pkg${withSize.length ? ` / ${Math.round(units * 1e6) / 1e6} units` : ""}${dates > 1 ? ` - ${dates} dates` : ""}</span>
        <button class="secondary" data-action="shop" data-name="${n}" title="Add to the Home Assistant shopping list">Shopping list</button>
        <button class="secondary" data-action="toggle-add" data-name="${n}">${open ? "Close" : "Add"}</button></div>
      ${open ? `<div class="fi-addrow" data-name="${n}">
        <input type="number" min="1" value="1" placeholder="Quantity" data-f="quantity" />
        <input type="number" min="0" step="any" placeholder="Per package" data-f="package_size" />
        <input type="date" data-f="best_before" />
        <button data-action="add-batch" data-name="${n}">Add</button></div>` : ""}
    </div>`;
  }

  _renderList() {
    const tab = this._tab();
    this._loc = tab.key;
    const tabs = this._tabs();
    const stateObj = this._hass.states[tab.entity];
    const items = this._items();
    const key =
      tab.key +
      JSON.stringify(tabs.map((t) => (this._hass.states[t.entity] || {}).attributes)) +
      JSON.stringify(tabs.map((t) => this._temp(t.key)));
    if (key === this._lastItems) return;
    this._lastItems = key;

    this.querySelector("#tabs").innerHTML = tabs
      .map((tb) => {
        const n = ((this._hass.states[tb.entity] || {}).attributes || {}).items || [];
        const t = this._temp(tb.key);
        return `<button data-loc="${this._esc(tb.key)}" class="${tb.key === tab.key ? "active" : ""}">${this._esc(tb.label)} (${n.length})${t ? `<br><small>${this._esc(t.text)}</small>` : ""}</button>`;
      })
      .join("");
    const cur = this._temp(tab.key);
    this.querySelector("#temp").innerHTML = cur
      ? `${this._esc(tab.label)} temperature: <b>${this._esc(cur.text)}</b>`
      : "";
    const place = this.querySelector("#place");
    const prevPlace = place.value;
    const keepPlace = this._placeFor === tab.key && tabs.some((tb) => tb.key === prevPlace);
    this._placeFor = tab.key;
    place.innerHTML = tabs
      .map((tb) => `<option value="${this._esc(tb.key)}"${tb.key === tab.key ? " selected" : ""}>${this._esc(tb.label)}</option>`)
      .join("");
    if (keepPlace) place.value = prevPlace;
    place.parentElement.style.display = tabs.length > 2 ? "" : "none";

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
      : `Entity ${tab.entity} not found. Is the integration set up?`;

    this.querySelector("#list").innerHTML = shown.length
      ? shown
          .map((i, idx) => {
            const isNew = idx === 0 || shown[idx - 1].name !== i.name;
            const head = isNew ? `${idx > 0 ? "</div>" : ""}<div class="fi-box">${this._groupHead(i.name, items)}` : "";
            const ref = `data-name="${this._esc(i.name)}" data-id="${this._esc(i.id)}"`;
            return `${head}
        <div class="fi-item">
          <div class="fi-info">
            <div class="fi-name">Batch</div>
            <div class="fi-meta">${this._expiry(i.best_before)}</div>
            <div class="fi-meta">Added ${this._esc(this._fmtDate(i.date_added))}</div>
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
          <button class="secondary" data-action="dec" ${ref} data-qty="${i.quantity}">-</button>
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
          .join("") + "</div>"
      : `<div class="fi-empty">${items.length ? "No matches." : `${tab.label} is empty.`}</div>`;
  }
}

customElements.define("freezer-inventory-panel", FreezerInventoryPanel);
