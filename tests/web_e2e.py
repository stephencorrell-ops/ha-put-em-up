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
            model.log_batch(**{k: v for k, v in data.items()})
        elif service == "save_recipe":
            model.save_recipe(data["name"], data["ingredients"], data["makes"], data.get("recipe_id"))
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
    page.add_script_tag(path=str(ROOT / "custom_components/put_em_up/www/put-em-up-card.js"))
    page.evaluate(SHIM)
    page.evaluate("s=>window.push(s)", model.snapshot())
    ok("Nothing in the pantry yet" in txt(), "empty pantry message")

    # recipe
    tab("recipes")
    sh("", "r.querySelector('[data-new-recipe]').click()")
    def fill(path, value):
        sh("", f"const e=r.querySelector('[data-f=\"{path}\"]');e.value={json.dumps(str(value))};e.dispatchEvent(new Event('change'))")
    fill("name", "Roasted salsa")
    fill("ings.0.name", "Tomatoes"); fill("ings.0.crop", "tomato"); fill("ings.0.lb", 10)
    sh("", "r.querySelector('[data-radd=ings]').click()")
    fill("ings.1.name", "Onions"); fill("ings.1.crop", "onion"); fill("ings.1.lb", 2); fill("ings.1.oz", 8)
    sh("", "r.querySelector('[data-radd=ings]').click()")
    fill("ings.2.name", "Vinegar"); fill("ings.2.oz", 6)
    fill("makes.0.name", "Salsa"); fill("makes.0.qty", 7)
    sh("", "r.querySelector('[data-save-recipe]').click()")
    page.wait_for_timeout(200)
    ok("Roasted salsa" in txt() and "2 lb 8 oz" in txt(), "recipe saved and shown in lb/oz")

    # triple batch
    tab("make")
    sh("", "const e=r.querySelector('[data-f=recipe_id]');e.value=e.options[1].value;e.dispatchEvent(new Event('change'))")
    sh("", "r.querySelector('[data-mult=\"3\"]').click()")
    ok("expected about 21 pints" in txt(), "triple batch expects 21 pints")
    v = sh("", "return r.querySelector('[data-f=\"ings.0.lb\"]').value")
    ok(v == "30", f"tomatoes scaled to 30 lb (got {v})")
    fill("prods.0.qty", 20)
    if SHOTS:
        page.screenshot(path=str(SHOTS / "make.png"), full_page=True)
    sh("", "r.querySelector('[data-save-batch]').click()")
    page.wait_for_timeout(200)
    ok("20" in txt() and "Salsa" in txt(), "pantry shows 20 pints of salsa")
    page.evaluate("document.getElementById('c').shadowRoot.querySelector('[data-use]').click()")
    page.wait_for_timeout(200)
    ok(model.snapshot()["pantry"][0]["count"] == 19, "eaten button takes one off")

    # shortfall
    tab("make")
    sh("", "r.querySelector('[data-add=ings]').click()")
    fill("ings.0.name", "Bell peppers"); fill("ings.0.crop", "bell_pepper"); fill("ings.0.lb", 60)
    ok("20 lb" in txt() and "shortfall" in txt(), "warns about 20 lb shortfall before saving")
    fill("prods.0.name", "Pepper relish"); fill("prods.0.qty", 30)
    sh("", "r.querySelector('[data-save-batch]').click()")
    page.wait_for_timeout(200)
    tab("garden")
    t = txt()
    ok("20 lb short" in t and "Total shortfall 2026" in t, "garden use shows 20 lb short")
    ok("Tomato" in t and "382 lb 8 oz left" in t.replace(" ", " "), "tomato left after 30 lb used")
    if SHOTS:
        page.screenshot(path=str(SHOTS / "garden.png"), full_page=True)
        tab("pantry"); page.screenshot(path=str(SHOTS / "pantry.png"), full_page=True)
    ok(not errors, f"no page errors {errors}")
    b.close()
print("web e2e OK")
