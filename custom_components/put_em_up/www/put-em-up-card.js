/* Put 'Em Up card: pantry, log a batch, batch history. */
(() => {
const DOMAIN = "put_em_up";
const CSS = `
:host{display:block}
ha-card{padding:12px}
.tabs{display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap}
.tab{padding:6px 14px;border-radius:16px;border:1px solid var(--divider-color);cursor:pointer;font-size:14px;background:none;color:var(--primary-text-color)}
.tab.on{background:var(--primary-color);color:var(--text-primary-color,#fff);border-color:var(--primary-color)}
.row{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 0;border-top:1px solid var(--divider-color)}
.row:first-of-type{border-top:0}
h3{margin:2px 0;font-size:16px}.sub{color:var(--secondary-text-color);font-size:12px}
.big{font-size:22px;font-weight:600}.low{color:var(--error-color,#b3501c)}
.btn{background:var(--primary-color);color:var(--text-primary-color,#fff);border:0;border-radius:16px;padding:6px 14px;cursor:pointer;font-size:13px}
.btn.ghost{background:none;color:var(--primary-color);border:1px solid var(--primary-color)}
.btn.sm{padding:3px 10px;font-size:12px}
.chip{display:inline-block;border:1px solid var(--divider-color);border-radius:14px;padding:4px 12px;margin:2px;cursor:pointer;font-size:13px;color:var(--primary-text-color);background:none}
.chip.on{background:var(--primary-color);color:var(--text-primary-color,#fff);border-color:var(--primary-color)}
input,select{background:var(--card-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color);border-radius:8px;padding:6px;font-size:14px;box-sizing:border-box}
.n{width:64px}.t{width:100%}.grow{flex:1;min-width:0}
.form{display:flex;flex-direction:column;gap:6px}
.line{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.bar{height:8px;background:var(--divider-color);border-radius:4px;margin:4px 0}.bar i{display:block;height:8px;border-radius:4px;background:var(--success-color,#4f7f33)}
.bar.short i{background:var(--error-color,#b3501c)}
.err{color:var(--error-color,#b3501c);font-size:13px}
.box{border:1px solid var(--divider-color);border-radius:10px;padding:10px;margin:6px 0}
`;
const fmt = (oz) => { const t = Math.round(oz || 0), lb = Math.floor(t / 16), o = t % 16; return lb && o ? `${lb} lb ${o} oz` : lb ? `${lb} lb` : `${o} oz`; };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const num = (v) => (v === "" || v == null ? 0 : Number(v));

class PutEmUpCard extends HTMLElement {
  setConfig() { this._tab = this._tab || "pantry"; if (!this.shadowRoot) this.attachShadow({ mode: "open" }); }
  getCardSize() { return 8; }
  set hass(h) {
    const first = !this._hass;
    this._hass = h;
    if (first) this._subscribe();
  }
  async _subscribe() {
    this._sub = await this._hass.connection.subscribeMessage((s) => { this._s = s; this._render(); }, { type: `${DOMAIN}/subscribe` });
  }
  disconnectedCallback() { if (this._sub) { this._sub(); this._sub = null; } }
  async _call(service, data) {
    this._err = "";
    try { await this._hass.callService(DOMAIN, service, data); return true; }
    catch (e) { this._err = e.message || String(e); this._render(); return false; }
  }

  _render() {
    if (!this._s || !this.shadowRoot) return;
    const s = this._s, tabs = [["pantry", "Pantry"], ["make", "Log a load"], ["totals", "Yearly totals"], ["history", "Loads"]];
    const body = { pantry: () => this._pantry(s), make: () => this._make(s), totals: () => this._totals(s), history: () => this._history(s) }[this._tab]();
    this.shadowRoot.innerHTML = `<style>${CSS}</style><ha-card>
      <div class="tabs">${tabs.map(([k, l]) => `<button class="tab ${k === this._tab ? "on" : ""}" data-tab="${k}">${l}</button>`).join("")}</div>
      ${this._err ? `<div class="err">${esc(this._err)}</div>` : ""}${body}</ha-card>`;
    this._wire();
  }

  // ---- pantry ----
  _pantry(s) {
    if (!s.pantry.length) return `<div class="sub">Nothing in the pantry yet. Log a batch and it shows up here.</div>`;
    const yr = (y) => `<div class="sub" style="margin-top:8px">${y}</div>`;
    let last = null, out = "";
    for (const i of s.pantry) {
      if (i.year !== last) { out += yr(i.year); last = i.year; }
      out += `<div class="row"><div><h3>${esc(i.name)}</h3><div class="sub">${esc(s.method_labels[i.method] || i.method)} · ${esc(i.unit)} · made ${i.made}</div></div>
        <div class="line"><span class="big ${i.count <= 3 ? "low" : ""}">${i.count}</span>
        <button class="btn sm" data-use="${esc(i.name)}|${i.unit}|${i.year}|eaten|${esc(i.method)}">−1 eaten</button>
        <button class="btn sm ghost" data-use="${esc(i.name)}|${i.unit}|${i.year}|gave away|${esc(i.method)}">gave</button>
        <button class="btn sm ghost" data-use="${esc(i.name)}|${i.unit}|${i.year}|found|${esc(i.method)}">+1</button></div></div>`;
    }
    return out;
  }

  // ---- log a batch ----
  _newMake(s) { return { crop: "", other: "", date: s.today, lb: "", oz: "", prods: [{ name: "", unit: "pints", method: "canning", qty: "" }] }; }
  _opts(list, value, labels) {
    return list.map((u) => `<option value="${esc(u)}" ${u === value ? "selected" : ""}>${esc((labels && labels[u]) || u)}</option>`).join("") + `<option value="__other" ${value === "__other" ? "selected" : ""}>Other…</option>`;
  }
  _prodRows(list, key, s, label) {
    const cap = (m) => ({ canning: "Canning", "freeze drying": "Freeze drying" }[m] || m.charAt(0).toUpperCase() + m.slice(1));
    return list.map((p, n) => `<div class="box"><div class="line">
      <input class="n" type="number" min="0" step="any" value="${p.qty ?? ""}" data-f="${key}.${n}.qty">
      <select data-f="${key}.${n}.unit">${this._opts(s.units, p.unit)}</select>
      <input class="grow" placeholder="${label}" value="${esc(p.name)}" data-f="${key}.${n}.name">
      <button class="btn sm ghost" data-del="${key}.${n}">✕</button></div>
      <div class="line"><span class="sub">Preserved by</span>
      <select data-f="${key}.${n}.method">${s.methods.map((m) => `<option value="${esc(m)}" ${m === p.method ? "selected" : ""}>${esc(cap(m))}</option>`).join("")}<option value="__other" ${p.method === "__other" ? "selected" : ""}>Other…</option></select>
      ${p.unit === "__other" ? `<input class="grow" placeholder="Measurement, e.g. bags" value="${esc(p.unit_other || "")}" data-f="${key}.${n}.unit_other">` : ""}
      ${p.method === "__other" ? `<input class="grow" placeholder="Method, e.g. smoking" value="${esc(p.method_other || "")}" data-f="${key}.${n}.method_other">` : ""}</div></div>`).join("");
  }
  _make(s) {
    const f = (this._m = this._m || this._newMake(s));
    const gc = s.garden_crops.find((c) => c.key === f.crop), cr = gc && s.crops.find((x) => x.key === f.crop), yr = String(f.date || s.today).slice(0, 4), row = cr && cr.years[yr];
    return `<div class="form">
      <div class="line"><span class="sub">Crop</span><select data-f="crop" class="grow"><option value="">Other…</option>${s.garden_crops.map((c) => `<option value="${c.key}" ${c.key === f.crop ? "selected" : ""}>🌱 ${esc(c.name)}</option>`).join("")}</select>
        <span class="sub">Date</span><input type="date" value="${f.date}" data-f="date"></div>
      ${f.crop ? "" : `<input class="t" placeholder="Crop name, e.g. Tomatoes" value="${esc(f.other)}" data-f="other">`}
      <div class="line"><span class="sub">Pounds in</span><input class="n" type="number" min="0" step="any" placeholder="lb" value="${f.lb ?? ""}" data-f="lb">lb
        <input class="n" type="number" min="0" step="any" placeholder="oz" value="${f.oz ?? ""}" data-f="oz">oz</div>
      ${row ? `<div class="sub">Garden Tracker logged ${fmt(row.harvested_oz)} of ${esc(gc.name)} in ${yr}.</div>` : ""}
      <div class="sub">What you made</div>${this._prodRows(f.prods, "prods", s, "Product, e.g. Salsa")}
      <div><button class="btn sm ghost" data-add="prods">+ product</button></div>
      <div><button class="btn" data-save-batch>Save load</button></div></div>`;
  }

  // ---- yearly totals ----
  _totals(s) {
    if (!s.totals.length) return `<div class="sub">No loads logged yet. Each load you log adds to the year's totals.</div>`;
    return s.totals.map((c) => `<div style="margin:6px 0 14px"><h3>${esc(c.name)}</h3>${c.years.map((y) => `<div class="box">
      <div class="line" style="justify-content:space-between"><b>${y.year}</b><span class="sub">${y.loads} load${y.loads === 1 ? "" : "s"} · ${fmt(y.oz)} in</span></div>
      ${y.products.map((p) => `<div class="row"><span>${esc(p.name)} <span class="sub">(${esc(s.method_labels[p.method] || p.method)})</span></span><span><b>${p.qty}</b> ${esc(p.unit)}${p.per_lb ? ` <span class="sub">· ${p.per_lb} per lb</span>` : ""}</span></div>`).join("")}</div>`).join("")}</div>`).join("");
  }

  // ---- batch history ----
  _history(s) {
    return s.batches.length ? s.batches.map((b) => `<div class="row"><div><h3>${esc((b.ingredients[0] && b.ingredients[0].name) || "Batch")} ${b.year}</h3>
      <div class="sub">${b.date}${b.total_oz ? ` · ${fmt(b.total_oz)} in` : ""}</div>
      <div class="sub">${b.products.map((p) => `${p.qty} ${esc(p.unit)} ${esc(p.name)} (${esc(s.method_labels[p.method] || p.method)})${p.per_lb ? ` (${p.per_lb} per lb)` : ""}`).join(", ")}</div></div>
      <button class="btn sm ghost" data-bdel="${b.id}">Delete</button></div>`).join("") : `<div class="sub">No loads yet.</div>`;
  }

  // ---- wiring ----
  _set(obj, path, v) { const p = path.split("."); let o = obj; for (let i = 0; i < p.length - 1; i++) o = o[p[i]]; o[p[p.length - 1]] = v; }
  _wire() {
    const R = this.shadowRoot, s = this._s;
    R.querySelectorAll("[data-tab]").forEach((b) => b.onclick = () => { this._tab = b.dataset.tab; this._err = ""; this._render(); });
    R.querySelectorAll("[data-use]").forEach((b) => b.onclick = () => { const [name, unit, year, kind, method] = b.dataset.use.split("|"); this._call("use_item", { name, unit, year: Number(year), qty: 1, kind, method }); });
    R.querySelectorAll("[data-bdel]").forEach((b) => b.onclick = () => { if (confirm("Delete this batch? Pantry counts and garden use go back.")) this._call("delete_batch", { batch_id: b.dataset.bdel }); });
    const form = () => this._m;
    R.querySelectorAll("[data-f]").forEach((el) => el.onchange = () => {
      const f = form(), path = el.dataset.f;
      const v = el.type === "number" ? (el.value === "" ? "" : Number(el.value)) : el.value;
      this._set(f, path, v);
      this._render();
    });
    R.querySelectorAll("[data-del]").forEach((b) => b.onclick = () => { const [k, n] = b.dataset.del.split("."); form()[k].splice(Number(n), 1); this._render(); });
    R.querySelectorAll("[data-add]").forEach((b) => b.onclick = () => { const last = this._m.prods[this._m.prods.length - 1] || {}; this._m.prods.push({ name: "", unit: last.unit || "pints", method: last.method || "canning", qty: "" }); this._render(); });
    const save = R.querySelector("[data-save-batch]");
    if (save) save.onclick = async () => {
      const f = this._m, gc = s.garden_crops.find((c) => c.key === f.crop), name = gc ? gc.name : (f.other || "").trim();
      const prods = f.prods.filter((p) => p.name.trim() && num(p.qty) > 0).map((p) => ({ name: p.name.trim(), unit: p.unit === "__other" ? (p.unit_other || "").trim() : p.unit, method: p.method === "__other" ? (p.method_other || "").trim() : p.method, qty: num(p.qty) }));
      const data = { products: prods, ingredients: name ? [{ name, crop: f.crop || null, crop_name: gc ? gc.name : null, lb: num(f.lb), oz: num(f.oz) }] : [], date: f.date || s.today };
      if (await this._call("log_batch", data)) { this._m = null; this._tab = "pantry"; this._render(); }
    };
  }
}
if (!customElements.get("put-em-up-card")) customElements.define("put-em-up-card", PutEmUpCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "put-em-up-card")) window.customCards.push({ type: "put-em-up-card", name: "Put 'Em Up", description: "Food preservation batches and pantry stock", preview: false });
})();
