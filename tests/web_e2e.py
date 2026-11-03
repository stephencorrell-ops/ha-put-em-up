"""Drives the real card in a browser against the real core model (no Home Assistant needed)."""
import json, sys
from datetime import date
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "put_em_up"))
from core.model import PantryModel, PantryError  # noqa: E402

GARDEN = {"tomato": {"name": "Tomato", "years": {"2026": 412.5}}, "onion": {"name": "Onion", "years": {"2026": 85.0}},
          "bell_pepper": {"name": "Bell pepper", "years": {"2026": 40.0}}}
model = PantryModel({}, lambda: date(2026, 11, 1))
model.garden = lambda: GARDEN
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else None

PAGE = "<body style='margin:0;background:#f4f4f0;width:520px;--primary-color:#4f7f33;--divider-color:#ddd;--secondary-text-color:#777;--primary-text-color:#222;--card-background-color:#fff'><put-em-up-card id=c></put-em-up-card>"
SHIM = """
window.__subs=[];
window.hass={connection:{subscribeMessage:async(cb)=>{window.__subs.push(cb);return ()=>{}}},
 callService:async(d,s,data)=>{const r=JSON.parse(await window.pyCall(s,JSON.stringify(data)));if(r.err)throw new Error(r.err);window.push(r.snap)}};
const c=document.getElementById('c');c.setConfig({});c.hass=window.hass;
window.push=(s)=>window.__subs.forEach(f=>f(s));
"""


def call(service, data):
    data = json.loads(data)
    try:
        if service == "log_batch":
            if "date" in data:
                data["on"] = data.pop("date")
            model.log_batch(**data)
        elif service == "use_item":
            model.use_item(**data)
        elif service == "delete_batch":
            model.delete_batch(data["batch_id"])
        elif service == "delete_recipe":
            model.delete_recipe(data["recipe_id"])
    except PantryError as e:
        return json.dumps({"err": str(e)})
    return json.dumps({"err": "", "snap": model.snapshot()})


def txt():
    return page.evaluate("document.getElementById('c').shadowRoot.textContent")


def tab(name):
    page.evaluate("n=>document.getElementById('c').shadowRoot.querySelector(`[data-tab=${n}]`).click()", name)


def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        sys.exit(1)


def sh(root_sel, js):
    return page.evaluate("([s,j])=>{const r=document.getElementById('c').shadowRoot;return (new Function('r',j))(r)}", [root_sel, js])


with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 520, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("dialog", lambda d: d.accept())
    page.expose_function("pyCall", call)
    page.set_content(PAGE)
    # Home Assistant loads every card as a plain script in one shared namespace, so load a card that
    # declares the same top-level names first: ours must still start.
    page.add_script_tag(content="const DOMAIN='garden_tracker';const esc=(s)=>s;const num=(n)=>n;const CSS='x';")
    page.add_script_tag(path=str(ROOT / "custom_components/put_em_up/www/put-em-up-card.js"))
    page.evaluate(SHIM)
    page.evaluate("s=>window.push(s)", model.snapshot())
    ok("Nothing in the pantry yet" in txt(), "empty pantry message")

    def fill(path, value):
        sh("", f"const e=r.querySelector('[data-f=\"{path}\"]');e.value={json.dumps(str(value))};e.dispatchEvent(new Event('change'))")
    # log a simple batch: crop, pounds in, products
    tab("make")
    ok("Garden Tracker logged" not in txt(), "no garden hint before a crop is picked")
    fill("crop", "tomato"); fill("lb", 400)
    ok("Garden Tracker logged 412 lb 8 oz of Tomato in 2026" in txt(), "shows what Garden Tracker logged for that crop")
    fill("prods.0.name", "Salsa"); fill("prods.0.qty", 140)
    sh("", "r.querySelector('[data-add=prods]').click()")
    fill("prods.1.name", "Diced tomatoes"); fill("prods.1.qty", 80)
    if SHOTS:
        page.screenshot(path=str(SHOTS / "make.png"), full_page=True)
    sh("", "r.querySelector('[data-save-batch]').click()")
    page.wait_for_timeout(200)
    t = txt()
    ok("140" in t and "Salsa" in t and "Diced tomatoes" in t, "pantry shows both products")
    page.evaluate("document.getElementById('c').shadowRoot.querySelector('[data-use]').click()")
    page.wait_for_timeout(200)
    counts = {i["name"]: i["count"] for i in model.snapshot()["pantry"]}
    ok(counts["Diced tomatoes"] == 79, f"eaten button takes one off (got {counts})")
    if SHOTS:
        page.screenshot(path=str(SHOTS / "pantry.png"), full_page=True)
    tab("history")
    t = txt()
    ok("Tomato 2026" in t and "400 lb in" in t and "0.35 per lb" in t, "batch history shows pounds in and yield per pound")
    if SHOTS:
        page.screenshot(path=str(SHOTS / "history.png"), full_page=True)
    # a second canner load the next weekend goes into the same totals
    tab("make")
    fill("crop", "tomato"); fill("date", "2026-09-12"); fill("lb", 200)
    fill("prods.0.name", "Salsa"); fill("prods.0.qty", 70)
    sh("", "r.querySelector('[data-save-batch]').click()")
    page.wait_for_timeout(200)
    salsa = [i for i in model.snapshot()["pantry"] if i["name"] == "Salsa"][0]
    ok(salsa["count"] == 210, f"second load adds to the pantry count (got {salsa['count']})")
    tab("totals")
    t = txt()
    ok("Tomato" in t and "2026" in t and "2 loads" in t and "600 lb in" in t and "210" in t and "0.2 per lb" in t and "0.133" not in t, "yearly totals add both loads")
    if SHOTS:
        page.screenshot(path=str(SHOTS / "totals.png"), full_page=True)
    # a crop that is not in the garden
    tab("make")
    t = txt()
    ok(all(w in t for w in ("Canning", "Freeze drying", "Drying", "Freezing", "Pickling", "Fermenting")), "all six preservation methods are offered")
    ok(all(w in t for w in ("half-pints", "pints", "quarts", "half-gallons", "gallons")), "all five measurements are offered")
    fill("other", "Peaches"); fill("lb", 30); fill("prods.0.name", "Peach halves"); fill("prods.0.unit", "quarts"); fill("prods.0.method", "freezing"); fill("prods.0.qty", 12)
    sh("", "r.querySelector('[data-add=prods]').click()")
    ok(sh("", "return r.querySelector('[data-f=\"prods.1.method\"]').value") == "freezing", "a new product row starts with the previous method")
    fill("prods.1.name", "Peach jerky"); fill("prods.1.qty", 6)
    fill("prods.1.unit", "__other"); fill("prods.1.unit_other", "Bags")
    fill("prods.1.method", "__other"); fill("prods.1.method_other", "Dehydrating")
    sh("", "r.querySelector('[data-save-batch]').click()")
    page.wait_for_timeout(200)
    tab("pantry")
    t = txt()
    ok("Peach halves" in t and "frozen" in t, "a crop not from the garden can be logged, shown as frozen")
    ok("Peach jerky" in t and "dehydrating" in t and "bags" in t, "a typed-in method and measurement are accepted")
    snap = model.snapshot()
    ok("dehydrating" in snap["methods"] and "bags" in snap["units"], "typed-in choices are remembered for next time")
    page.evaluate("[...document.getElementById('c').shadowRoot.querySelectorAll('[data-use]')].find(b=>b.dataset.use.startsWith('Peach halves')).click()")
    page.wait_for_timeout(200)
    ok({(i["name"], i["method"]): i["count"] for i in model.snapshot()["pantry"]}[("Peach halves", "freezing")] == 11, "eating a frozen item takes one off the frozen count")
    if SHOTS:
        page.screenshot(path=str(SHOTS / "pantry2.png"), full_page=True)
        tab("make"); page.screenshot(path=str(SHOTS / "make2.png"), full_page=True)
    ok("Recipes" not in txt() and "Garden use" not in txt(), "recipes and garden use tabs are gone")
    ok(not errors, f"no page errors {errors}")
    b.close()
print("web e2e OK")
