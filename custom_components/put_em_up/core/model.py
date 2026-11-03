"""Put 'Em Up: recipes, batches and pantry stock. No Home Assistant imports, so it can be tested alone.

Everything is stored as weights in ounces; pantry counts and garden "left"/"shortfall" are worked
out from the logs each time, so deleting a batch or a use puts everything back by itself.
"""
from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Callable

UNITS = ["half-pints", "pints", "quarts", "half-gallons", "gallons", "bags", "jars", "pounds"]
USE_KINDS = ["eaten", "gave away", "spoiled", "found"]  # "found" adds one back
OZ_PER_LB = 16.0


class PantryError(Exception):
    pass


def to_oz(lb=0, oz=0) -> float:
    try:
        v = float(lb or 0) * OZ_PER_LB + float(oz or 0)
    except (TypeError, ValueError):
        raise PantryError("Weights must be numbers (pounds and ounces)")
    if v < 0:
        raise PantryError("A weight can't be negative")
    return round(v, 2)


def fmt_oz(oz: float) -> str:
    """3.25 lb -> '3 lb 4 oz'."""
    total = round(float(oz))
    lb, rest = divmod(total, 16)
    if lb and rest:
        return f"{lb} lb {rest} oz"
    return f"{lb} lb" if lb else f"{rest} oz"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def _clean(s, what="Name") -> str:
    s = str(s or "").strip()
    if not s:
        raise PantryError(f"{what} is required")
    return s


def _qty(q, what="Amount") -> float:
    try:
        v = float(q)
    except (TypeError, ValueError):
        raise PantryError(f"{what} must be a number")
    if v <= 0:
        raise PantryError(f"{what} must be more than zero")
    return round(v, 2)


def item_key(name: str, unit: str, year: int) -> str:
    return f"{slug(name)}|{unit}|{year}"


class PantryModel:
    def __init__(self, data: dict | None, today: Callable[[], date], on_change=lambda: None, on_structure=lambda: None):
        self.data = data or {}
        for k in ("recipes", "batches", "uses"):
            self.data.setdefault(k, {})
        self.today = today
        self._changed, self._structure = on_change, on_structure
        self.garden: Callable[[], dict] = lambda: {}  # crop key -> {"name", "years": {"2026": lbs}}

    # ---- helpers --------------------------------------------------------------------
    def _id(self) -> str:
        return uuid.uuid4().hex[:8]

    def _ingredients(self, rows) -> list[dict]:
        out = []
        for r in rows or []:
            name = _clean(r.get("name") or r.get("crop_name"), "Ingredient name")
            oz = to_oz(r.get("lb"), r.get("oz")) if ("lb" in r or "oz" in r) else to_oz(0, r.get("total_oz", 0))
            crop = r.get("crop") or None
            if crop:
                crop = slug(crop)
            out.append({"name": name, "crop": crop, "crop_name": r.get("crop_name") or (name if crop else None), "oz": oz})
        return out

    def _products(self, rows) -> list[dict]:
        out = []
        for r in rows or []:
            unit = r.get("unit", "pints")
            if unit not in UNITS:
                raise PantryError(f"Unit must be one of: {', '.join(UNITS)}")
            out.append({"name": _clean(r.get("name"), "Product name"), "unit": unit, "qty": _qty(r.get("qty"), "Number made")})
        if not out:
            raise PantryError("Add at least one product")
        return out

    # ---- recipes ---------------------------------------------------------------------
    def save_recipe(self, name, ingredients, makes, recipe_id=None) -> str:
        rid = recipe_id or self._id()
        if recipe_id and recipe_id not in self.data["recipes"]:
            raise PantryError("No such recipe")
        self.data["recipes"][rid] = {"id": rid, "name": _clean(name, "Recipe name"),
                                     "ingredients": self._ingredients(ingredients), "makes": self._products(makes)}
        self._structure()
        return rid

    def delete_recipe(self, recipe_id) -> None:
        if self.data["recipes"].pop(recipe_id, None) is None:
            raise PantryError("No such recipe")
        self._structure()

    # ---- batches ---------------------------------------------------------------------
    def log_batch(self, products, ingredients=None, recipe_id=None, multiplier=1, year=None, on=None, notes="") -> str:
        """products are what you actually got; ingredients are the totals used (already scaled).
        With a recipe and no ingredients given, the recipe's amounts are multiplied."""
        mult = _qty(multiplier, "Batch size")
        recipe = None
        if recipe_id:
            recipe = self.data["recipes"].get(recipe_id)
            if recipe is None:
                raise PantryError("No such recipe")
        if ingredients is None:
            if recipe is None:
                raise PantryError("Add the ingredients you used")
            ings = [{**i, "oz": round(i["oz"] * mult, 2)} for i in recipe["ingredients"]]
        else:
            ings = self._ingredients(ingredients)
        day = on or self.today().isoformat()
        bid = self._id()
        self.data["batches"][bid] = {
            "id": bid, "date": str(day), "year": int(year or str(day)[:4]),
            "recipe_id": recipe_id, "recipe_name": recipe["name"] if recipe else None, "multiplier": mult,
            "ingredients": ings, "products": self._products(products), "notes": str(notes or "")}
        self._structure()
        return bid

    def delete_batch(self, batch_id) -> None:
        if self.data["batches"].pop(batch_id, None) is None:
            raise PantryError("No such batch")
        self._structure()

    # ---- pantry use ------------------------------------------------------------------
    def use_item(self, name, unit, year, qty=1, kind="eaten", on=None) -> str:
        if kind not in USE_KINDS:
            raise PantryError(f"Kind must be one of: {', '.join(USE_KINDS)}")
        key = item_key(name, unit, int(year))
        if key not in self._stock():
            raise PantryError("No such pantry item")
        n = _qty(qty)
        if kind != "found" and n > self._stock()[key]["count"] + 1e-9:
            raise PantryError(f"Only {self._stock()[key]['count']:g} left")
        uid = self._id()
        self.data["uses"][uid] = {"id": uid, "key": key, "qty": n, "kind": kind, "date": str(on or self.today().isoformat())}
        self._changed()
        return uid

    def delete_use(self, use_id) -> None:
        if self.data["uses"].pop(use_id, None) is None:
            raise PantryError("No such entry")
        self._changed()

    # ---- derived ---------------------------------------------------------------------
    def _stock(self) -> dict:
        items: dict[str, dict] = {}
        for b in self.data["batches"].values():
            for p in b["products"]:
                k = item_key(p["name"], p["unit"], b["year"])
                it = items.setdefault(k, {"key": k, "name": p["name"], "unit": p["unit"], "year": b["year"], "made": 0.0, "out": 0.0})
                it["made"] += p["qty"]
        for u in self.data["uses"].values():
            it = items.get(u["key"])
            if it is None:
                continue
            if u["kind"] == "found":
                it["made"] += u["qty"]
            else:
                it["out"] += u["qty"]
        for it in items.values():
            it["count"] = round(it["made"] - it["out"], 2)
        return items

    def crop_ledger(self) -> dict:
        """Per crop and year: harvested (from Garden Tracker), used in batches, left, shortfall."""
        garden = self.garden() or {}
        used: dict[tuple, float] = {}
        names: dict[str, str] = {k: g.get("name", k) for k, g in garden.items()}
        for b in self.data["batches"].values():
            for i in b["ingredients"]:
                if i["crop"]:
                    used[(i["crop"], str(b["year"]))] = used.get((i["crop"], str(b["year"])), 0.0) + i["oz"]
                    names.setdefault(i["crop"], i.get("crop_name") or i["name"])
        crops: dict[str, dict] = {}
        for key in set(names):
            years = set((garden.get(key) or {}).get("years", {})) | {y for (c, y) in used if c == key}
            rows = {}
            for y in sorted(years, reverse=True):
                got = round(float(((garden.get(key) or {}).get("years") or {}).get(y, 0.0)) * OZ_PER_LB, 2)
                u = round(used.get((key, y), 0.0), 2)
                rows[y] = {"harvested_oz": got, "used_oz": u, "left_oz": round(max(got - u, 0.0), 2),
                           "short_oz": round(max(u - got, 0.0), 2)}
            crops[key] = {"key": key, "name": names[key], "years": rows}
        return crops

    def totals(self) -> list[dict]:
        """Per crop, per year: loads, pounds in, and everything made, added up across all loads."""
        crops: dict[str, dict] = {}
        for b in self.data["batches"].values():
            ing = b["ingredients"][0] if b["ingredients"] else None
            name = (ing["name"] if ing else None) or "Unnamed"
            key = (ing.get("crop") if ing else None) or slug(name)
            c = crops.setdefault(key, {"key": key, "name": name, "years": {}})
            y = c["years"].setdefault(str(b["year"]), {"year": b["year"], "loads": 0, "oz": 0.0, "made": {}})
            y["loads"] += 1
            load_oz = sum(i["oz"] for i in b["ingredients"])
            y["oz"] += load_oz
            seen = set()
            for p in b["products"]:
                k = (p["name"].strip().lower(), p["unit"])
                m = y["made"].setdefault(k, {"name": p["name"], "unit": p["unit"], "qty": 0.0, "oz": 0.0})
                m["qty"] = round(m["qty"] + p["qty"], 2)
                if k not in seen:  # jars per pound only counts the loads that actually made the product
                    m["oz"] += load_oz
                    seen.add(k)
        out = []
        for c in sorted(crops.values(), key=lambda c: c["name"].lower()):
            years = []
            for y in sorted(c["years"].values(), key=lambda y: -y["year"]):
                prods = [{"name": m["name"], "unit": m["unit"], "qty": m["qty"],
                          "per_lb": round(m["qty"] / (m["oz"] / OZ_PER_LB), 3) if m["oz"] else None}
                         for m in sorted(y["made"].values(), key=lambda m: (m["name"].lower(), m["unit"]))]
                years.append({"year": y["year"], "loads": y["loads"], "oz": round(y["oz"], 2), "products": prods})
            out.append({"key": c["key"], "name": c["name"], "years": years})
        return out

    def snapshot(self) -> dict:
        today = self.today()
        year = str(today.year)
        stock = sorted(self._stock().values(), key=lambda i: (-i["year"], i["name"].lower()))
        crops = self.crop_ledger()
        short_by_year: dict[str, float] = {}
        for c in crops.values():
            for y, r in c["years"].items():
                short_by_year[y] = round(short_by_year.get(y, 0.0) + r["short_oz"], 2)
        batches = []
        for b in sorted(self.data["batches"].values(), key=lambda b: b["date"], reverse=True):
            total_oz = sum(i["oz"] for i in b["ingredients"])
            prods = [{**p, "per_lb": round(p["qty"] / (total_oz / 16), 3) if total_oz else None} for p in b["products"]]
            batches.append({**b, "products": prods, "total_oz": round(total_oz, 2)})
        return {
            "today": today.isoformat(), "year": int(year), "units": UNITS, "use_kinds": USE_KINDS,
            "pantry": stock,
            "recipes": sorted(self.data["recipes"].values(), key=lambda r: r["name"].lower()),
            "batches": batches,
            "totals": self.totals(),
            "uses": sorted(self.data["uses"].values(), key=lambda u: u["date"], reverse=True),
            "crops": sorted(crops.values(), key=lambda c: c["name"].lower()),
            "garden_crops": sorted(({"key": k, "name": g.get("name", k)} for k, g in (self.garden() or {}).items()), key=lambda c: c["name"].lower()),
            "short_by_year": short_by_year,
            "short_this_year_oz": short_by_year.get(year, 0.0),
        }
