/* Put 'Em Up card: pantry, make a batch, recipes, garden use. */
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
const split = (oz) => ({ lb: Math.floor(oz / 16), oz: Math.round((oz % 16) * 100) / 100 });
const q = (n) => Math.round(n * 100) / 100;

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
    const s = this._s, tabs = [["pantry", "Pantry"], ["make", "Make a batch"], ["recipes", "Recipes"], ["garden", "Garden use"], ["history", "Batches"]];
    const body = { pantry: () => this._pantry(s), make: () => this._make(s), recipes: () => this._recipes(s), garden: () => this._garden(s), history: () => this._history(s) }[this._tab]();
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
      out += `<div class="row"><div><h3>${esc(i.name)}</h3><div class="sub">${esc(i.unit)} · made ${i.made}</div></div>
        <div class="line"><span class="big ${i.count <= 3 ? "low" : ""}">${i.count}</span>
        <button class="btn sm" data-use="${esc(i.name)}|${i.unit}|${i.year}|eaten">−1 eaten</button>
        <button class="btn sm ghost" data-use="${esc(i.name)}|${i.unit}|${i.year}|gave away">gave</button>
        <button class="btn sm ghost" data-use="${esc(i.name)}|${i.unit}|${i.year}|found">+1</button></div></div>`;
    }
    return out;
  }

  // ---- make a batch ----
  _newMake(s) { return { recipe_id: "", mult: 1, year: s.year, ings: [], prods: [{ name: "", unit: "pints", qty: "" }] }; }
  _applyRecipe(s) {
    const f = this._m, r = s.recipes.find((x) => x.id === f.recipe_id);
    if (!r) return;
    f.ings = r.ingredients.map((i) => ({ name: i.name, crop: i.crop || "", crop_name: i.crop_name || "", ...split(q(i.oz * f.mult)) }));
    f.prods = r.makes.map((p) => ({ name: p.name, unit: p.unit, qty: q(p.qty * f.mult) }));
  }
  _ingRows(list, key, s) {
    return list.map((i, n) => `<div class="line">
      <input class="grow" placeholder="Ingredient" value="${esc(i.name)}" data-f="${key}.${n}.name">
      <select data-f="${key}.${n}.crop"><option value="">Not from garden</option>${s.garden_crops.map((c) => `<option value="${c.key}" ${c.key === i.crop ? "selected" : ""}>🌱 ${esc(c.name)}</option>`).join("")}</select>
      <input class="n" type="number" min="0" step="any" placeholder="lb" value="${i.lb ?? ""}" data-f="${key}.${n}.lb">lb
      <input class="n" type="number" min="0" step="any" placeholder="oz" value="${i.oz ?? ""}" data-f="${key}.${n}.oz">oz
      <button class="btn sm ghost" data-del="${key}.${n}">✕</button></div>`).join("");
  }
  _prodRows(list, key, s, label) {
    return list.map((p, n) => `<div class="line">
      <input class="n" type="number" min="0" step="any" value="${p.qty ?? ""}" data-f="${key}.${n}.qty">
      <select data-f="${key}.${n}.unit">${s.units.map((u) => `<option ${u === p.unit ? "selected" : ""}>${u}</option>`).join("")}</select>
      <input class="grow" placeholder="${label}" value="${esc(p.name)}" data-f="${key}.${n}.name">
      <button class="btn sm ghost" data-del="${key}.${n}">✕</button></div>`).join("");
  }
  _make(s) {
    const f = (this._m = this._m || this._newMake(s));
    const r = s.recipes.find((x) => x.id === f.recipe_id);
    const mults = [1, 2, 3, 4];
    const useOz = (c) => f.ings.filter((i) => i.crop === c).reduce((a, i) => a + num(i.lb) * 16 + num(i.oz), 0);
    const warn = [...new Set(f.ings.filter((i) => i.crop).map((i) => i.crop))].map((c) => {
      const cr = s.crops.find((x) => x.key === c), row = cr && cr.years[String(f.year)];
      const left = row ? row.left_oz : 0, need = useOz(c);
      return need > left ? `<div class="err">${esc(cr ? cr.name : c)}: using ${fmt(need)} but only ${fmt(left)} left from ${f.year} — that adds ${fmt(need - left)} to the shortfall.</div>` : "";
    }).join("");
    return `<div class="form">
      <div class="line"><span class="sub">Recipe</span><select data-f="recipe_id" class="grow"><option value="">None (one-off batch)</option>${s.recipes.map((x) => `<option value="${x.id}" ${x.id === f.recipe_id ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select>
        <span class="sub">Year</span><input class="n" type="number" value="${f.year}" data-f="year"></div>
      ${r ? `<div class="line"><span class="sub">How many batches</span>${mults.map((m) => `<button class="chip ${f.mult === m ? "on" : ""}" data-mult="${m}">${m}×</button>`).join("")}
        <input class="n" type="number" min="0" step="any" value="${mults.includes(f.mult) ? "" : f.mult}" placeholder="other" data-f="mult"></div>` : ""}
      <div class="sub">Ingredients used</div>${this._ingRows(f.ings, "ings", s)}
      <div><button class="btn sm ghost" data-add="ings">+ ingredient</button></div>${warn}
      <div class="sub">What you made${r ? ` (expected about ${r.makes.map((p) => `${q(p.qty * f.mult)} ${p.unit}`).join(", ")})` : ""}</div>${this._prodRows(f.prods, "prods", s, "Product, e.g. Salsa")}
      <div><button class="btn sm ghost" data-add="prods">+ product</button></div>
      <div><button class="btn" data-save-batch>Save batch</button></div></div>`;
  }

  // ---- recipes ----
  _recipes(s) {
    const f = this._r;
    if (f) return `<div class="form">
      <input class="t" placeholder="Recipe name" value="${esc(f.name)}" data-f="name">
      <div class="sub">Ingredients for one batch (garden items are counted against your harvest)</div>${this._ingRows(f.ings, "ings", s)}
      <div><button class="btn sm ghost" data-radd="ings">+ ingredient</button></div>
      <div class="sub">One batch makes</div>${this._prodRows(f.makes, "makes", s, "Product, e.g. Salsa")}
      <div><button class="btn sm ghost" data-radd="makes">+ product</button></div>
      <div class="line"><button class="btn" data-save-recipe>Save recipe</button><button class="btn ghost" data-cancel>Cancel</button></div></div>`;
    return (s.recipes.length ? s.recipes.map((r) => `<div class="row"><div><h3>${esc(r.name)}</h3>
      <div class="sub">${r.ingredients.map((i) => `${esc(i.name)} ${fmt(i.oz)}${i.crop ? " 🌱" : ""}`).join(" · ")}</div>
      <div class="sub">Makes ${r.makes.map((p) => `${p.qty} ${p.unit} ${esc(p.name)}`).join(", ")}</div></div>
      <div class="line"><button class="btn sm" data-edit="${r.id}">Edit</button><button class="btn sm ghost" data-rdel="${r.id}">Delete</button></div></div>`).join("")
      : `<div class="sub">No recipes yet.</div>`) + `<div style="margin-top:8px"><button class="btn" data-new-recipe>+ New recipe</button></div>`;
  }

  // ---- garden use ----
  _garden(s) {
    const yr = String(s.year);
    const short = s.short_by_year[yr] || 0;
    const rows = s.crops.filter((c) => c.years[yr]).map((c) => {
      const r = c.years[yr], pct = r.harvested_oz ? Math.min(100, (r.used_oz / r.harvested_oz) * 100) : (r.used_oz ? 100 : 0);
      return `<div style="margin:10px 0"><b>${esc(c.name)}</b> <span class="sub">${fmt(r.harvested_oz)} harvested</span>
        <div class="bar ${r.short_oz ? "short" : ""}"><i style="width:${pct}%"></i></div>
        <span class="sub">${fmt(r.used_oz)} used · </span>${r.short_oz ? `<b class="low">${fmt(r.short_oz)} short</b>` : `<b>${fmt(r.left_oz)} left</b>`}</div>`;
    }).join("");
    const older = Object.entries(s.short_by_year).filter(([y, v]) => y !== yr && v > 0).map(([y, v]) => `${y}: ${fmt(v)}`).join(" · ");
    return `<div class="sub">${yr}: harvested → used in batches → left</div>${rows || `<div class="sub">No garden crops used in batches yet.</div>`}
      <div class="row"><b>Total shortfall ${yr}</b><span class="big ${short ? "low" : ""}">${fmt(short)}</span></div>
      ${older ? `<div class="sub">Earlier years: ${older}</div>` : ""}`;
  }

  // ---- batch history ----
  _history(s) {
    return s.batches.length ? s.batches.map((b) => `<div class="row"><div><h3>${esc(b.recipe_name || "One-off batch")}${b.multiplier !== 1 ? ` ×${b.multiplier}` : ""}</h3>
      <div class="sub">${b.date} · ${fmt(b.total_oz)} in</div>
      <div class="sub">${b.products.map((p) => `${p.qty} ${p.unit} ${esc(p.name)}${p.per_lb ? ` (${p.per_lb} per lb)` : ""}`).join(", ")}</div></div>
      <button class="btn sm ghost" data-bdel="${b.id}">Delete</button></div>`).join("") : `<div class="sub">No batches yet.</div>`;
  }

  // ---- wiring ----
  _set(obj, path, v) { const p = path.split("."); let o = obj; for (let i = 0; i < p.length - 1; i++) o = o[p[i]]; o[p[p.length - 1]] = v; }
  _ings(list, s) { return list.filter((i) => i.name.trim()).map((i) => ({ name: i.name.trim(), crop: i.crop || null, crop_name: i.crop ? (s.garden_crops.find((c) => c.key === i.crop) || {}).name || null : null, lb: num(i.lb), oz: num(i.oz) })); }
  _wire() {
    const R = this.shadowRoot, s = this._s;
    R.querySelectorAll("[data-tab]").forEach((b) => b.onclick = () => { this._tab = b.dataset.tab; this._err = ""; this._render(); });
    R.querySelectorAll("[data-use]").forEach((b) => b.onclick = () => { const [name, unit, year, kind] = b.dataset.use.split("|"); this._call("use_item", { name, unit, year: Number(year), qty: 1, kind }); });
    R.querySelectorAll("[data-bdel]").forEach((b) => b.onclick = () => { if (confirm("Delete this batch? Pantry counts and garden use go back.")) this._call("delete_batch", { batch_id: b.dataset.bdel }); });
    R.querySelectorAll("[data-rdel]").forEach((b) => b.onclick = () => { if (confirm("Delete this recipe? Past batches stay.")) this._call("delete_recipe", { recipe_id: b.dataset.rdel }); });
    const form = () => (this._tab === "make" ? this._m : this._r);
    R.querySelectorAll("[data-f]").forEach((el) => el.onchange = () => {
      const f = form(), path = el.dataset.f;
      const v = el.type === "number" ? (el.value === "" ? "" : Number(el.value)) : el.value;
      this._set(f, path, v);
      if (this._tab === "make" && (path === "recipe_id" || path === "mult")) { if (path === "mult" && !v) f.mult = 1; if (path === "recipe_id") f.mult = 1; this._applyRecipe(s); }
      this._render();
    });
    R.querySelectorAll("[data-mult]").forEach((b) => b.onclick = () => { this._m.mult = Number(b.dataset.mult); this._applyRecipe(s); this._render(); });
    R.querySelectorAll("[data-del]").forEach((b) => b.onclick = () => { const [k, n] = b.dataset.del.split("."); form()[k].splice(Number(n), 1); this._render(); });
    R.querySelectorAll("[data-add]").forEach((b) => b.onclick = () => { const k = b.dataset.add; this._m[k].push(k === "ings" ? { name: "", crop: "", lb: "", oz: "" } : { name: "", unit: "pints", qty: "" }); this._render(); });
    R.querySelectorAll("[data-radd]").forEach((b) => b.onclick = () => { const k = b.dataset.radd; this._r[k].push(k === "ings" ? { name: "", crop: "", lb: "", oz: "" } : { name: "", unit: "pints", qty: "" }); this._render(); });
    const save = R.querySelector("[data-save-batch]");
    if (save) save.onclick = async () => {
      const f = this._m, prods = f.prods.filter((p) => p.name.trim() && num(p.qty) > 0).map((p) => ({ name: p.name.trim(), unit: p.unit, qty: num(p.qty) }));
      const data = { products: prods, ingredients: this._ings(f.ings, s), year: Number(f.year) || s.year, multiplier: f.mult || 1 };
      if (f.recipe_id) data.recipe_id = f.recipe_id;
      if (await this._call("log_batch", data)) { this._m = null; this._tab = "pantry"; this._render(); }
    };
    R.querySelectorAll("[data-new-recipe]").forEach((b) => b.onclick = () => { this._r = { id: "", name: "", ings: [{ name: "", crop: "", lb: "", oz: "" }], makes: [{ name: "", unit: "pints", qty: "" }] }; this._render(); });
    R.querySelectorAll("[data-edit]").forEach((b) => b.onclick = () => {
      const r = s.recipes.find((x) => x.id === b.dataset.edit);
      this._r = { id: r.id, name: r.name, ings: r.ingredients.map((i) => ({ name: i.name, crop: i.crop || "", ...split(i.oz) })), makes: r.makes.map((p) => ({ ...p })) };
      this._render();
    });
    R.querySelectorAll("[data-cancel]").forEach((b) => b.onclick = () => { this._r = null; this._render(); });
    const sr = R.querySelector("[data-save-recipe]");
    if (sr) sr.onclick = async () => {
      const f = this._r, data = { name: f.name, ingredients: this._ings(f.ings, s), makes: f.makes.filter((p) => p.name.trim() && num(p.qty) > 0).map((p) => ({ name: p.name.trim(), unit: p.unit, qty: num(p.qty) })) };
      if (f.id) data.recipe_id = f.id;
      if (await this._call("save_recipe", data)) { this._r = null; this._render(); }
    };
  }
}
if (!customElements.get("put-em-up-card")) customElements.define("put-em-up-card", PutEmUpCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "put-em-up-card")) window.customCards.push({ type: "put-em-up-card", name: "Put 'Em Up", description: "Food preservation batches, recipes, pantry stock and garden use", preview: false });
})();
