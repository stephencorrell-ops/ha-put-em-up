import sys, unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "put_em_up"))
import importlib.util as _u  # the standard library has a module called resource; load ours by path
_s = _u.spec_from_file_location("resource", str(Path(__file__).resolve().parents[1] / "custom_components" / "put_em_up" / "resource.py"))
_m = _u.module_from_spec(_s); _s.loader.exec_module(_m); sys.modules["resource"] = _m
from core.model import PantryModel, PantryError, to_oz, fmt_oz  # noqa: E402

GARDEN = {"tomato": {"name": "Tomato", "years": {"2026": 412.5}},
          "bell_pepper": {"name": "Bell pepper", "years": {"2026": 40.0}},
          "onion": {"name": "Onion", "years": {"2026": 85.0}}}


def make():
    m = PantryModel({}, lambda: date(2026, 11, 1))
    m.garden = lambda: GARDEN
    return m


SALSA = [{"name": "Tomatoes", "crop": "tomato", "crop_name": "Tomato", "lb": 10},
         {"name": "Onions", "crop": "onion", "crop_name": "Onion", "lb": 2, "oz": 8},
         {"name": "Vinegar", "lb": 0, "oz": 6}]


class Weights(unittest.TestCase):
    def test_conversion(self):
        self.assertEqual(to_oz(3, 4), 52)
        self.assertEqual(fmt_oz(52), "3 lb 4 oz")
        self.assertEqual(fmt_oz(16), "1 lb")
        self.assertEqual(fmt_oz(5), "5 oz")
        with self.assertRaises(PantryError):
            to_oz(-1, 0)


class Batches(unittest.TestCase):
    def test_multiplier_scales_ingredients(self):
        m = make()
        rid = m.save_recipe("Salsa", SALSA, [{"name": "Salsa", "unit": "pints", "qty": 7}])
        m.log_batch([{"name": "Salsa", "unit": "pints", "qty": 20}], recipe_id=rid, multiplier=3)
        b = m.snapshot()["batches"][0]
        self.assertEqual([i["oz"] for i in b["ingredients"]], [480, 120, 18])
        led = {c["key"]: c["years"]["2026"] for c in m.snapshot()["crops"]}
        self.assertEqual(led["tomato"]["used_oz"], 480)
        self.assertEqual(led["tomato"]["left_oz"], 412.5 * 16 - 480)
        self.assertNotIn("vinegar", led)  # not a garden crop, not counted

    def test_shortfall(self):
        m = make()
        m.log_batch([{"name": "Pepper relish", "unit": "pints", "qty": 30}],
                    ingredients=[{"name": "Bell peppers", "crop": "bell_pepper", "crop_name": "Bell pepper", "lb": 60}])
        s = m.snapshot()
        row = {c["key"]: c["years"]["2026"] for c in s["crops"]}["bell_pepper"]
        self.assertEqual(row["short_oz"], 20 * 16)
        self.assertEqual(row["left_oz"], 0)
        self.assertEqual(s["short_this_year_oz"], 320)

    def test_delete_batch_restores(self):
        m = make()
        bid = m.log_batch([{"name": "X", "unit": "pints", "qty": 2}], ingredients=[{"name": "T", "crop": "tomato", "lb": 5}])
        m.delete_batch(bid)
        s = m.snapshot()
        self.assertEqual(s["pantry"], [])
        self.assertEqual({c["key"]: c["years"]["2026"]["used_oz"] for c in s["crops"]}["tomato"], 0)

    def test_yield_per_pound(self):
        m = make()
        m.log_batch([{"name": "Salsa", "unit": "pints", "qty": 14}], ingredients=[{"name": "T", "crop": "tomato", "lb": 40}])
        self.assertAlmostEqual(m.snapshot()["batches"][0]["products"][0]["per_lb"], 0.35)

    def test_validation(self):
        m = make()
        with self.assertRaises(PantryError):
            m.log_batch([], ingredients=[{"name": "T", "lb": 1}])
        with self.assertRaises(PantryError):
            m.log_batch([{"name": "S", "unit": "buckets", "qty": 1}], ingredients=[])
        with self.assertRaises(PantryError):
            m.log_batch([{"name": "S", "unit": "pints", "qty": 1}], recipe_id=None)


class YearTotals(unittest.TestCase):
    def test_loads_add_up_by_crop_and_year(self):
        m = make()
        T = {"name": "Tomatoes", "crop": "tomato", "crop_name": "Tomato"}
        m.log_batch([{"name": "Salsa", "unit": "pints", "qty": 70}], ingredients=[{**T, "lb": 200}], on="2026-09-05")
        m.log_batch([{"name": "salsa", "unit": "pints", "qty": 70}, {"name": "Diced", "unit": "pints", "qty": 40}],
                    ingredients=[{**T, "lb": 200}], on="2026-09-12")
        m.log_batch([{"name": "Salsa", "unit": "pints", "qty": 90}], ingredients=[{**T, "lb": 300}], on="2025-09-10")
        tot = {t["key"]: t for t in m.snapshot()["totals"]}["tomato"]
        y26, y25 = tot["years"]
        self.assertEqual((y26["year"], y26["loads"], y26["oz"]), (2026, 2, 400 * 16))
        salsa = [p for p in y26["products"] if p["name"].lower() == "salsa"][0]
        self.assertEqual((salsa["qty"], salsa["per_lb"]), (140, 0.35))
        self.assertEqual((y25["year"], y25["products"][0]["per_lb"]), (2025, 0.3))
        diced = [p for p in y26["products"] if p["name"] == "Diced"][0]
        self.assertEqual(diced["per_lb"], 0.2)  # 40 pints from the one load (200 lb) that made it
        # the pantry adds the two 2026 loads together as well
        self.assertEqual({i["name"].lower(): i["count"] for i in m.snapshot()["pantry"] if i["year"] == 2026}["salsa"], 140)

    def test_date_sets_the_year(self):
        m = make()
        m.log_batch([{"name": "Jam", "unit": "pints", "qty": 5}], ingredients=[{"name": "Berries", "lb": 10}], on="2025-07-04")
        self.assertEqual(m.snapshot()["batches"][0]["year"], 2025)


class Pantry(unittest.TestCase):
    def test_use_and_found(self):
        m = make()
        m.log_batch([{"name": "Salsa", "unit": "pints", "qty": 5}], ingredients=[{"name": "T", "crop": "tomato", "lb": 5}])
        m.use_item("Salsa", "pints", 2026, 2)
        self.assertEqual(m.snapshot()["pantry"][0]["count"], 3)
        u = m.use_item("Salsa", "pints", 2026, 1, "found")
        self.assertEqual(m.snapshot()["pantry"][0]["count"], 4)
        m.delete_use(u)
        self.assertEqual(m.snapshot()["pantry"][0]["count"], 3)
        with self.assertRaises(PantryError):
            m.use_item("Salsa", "pints", 2026, 9)

    def test_years_kept_apart(self):
        m = make()
        for y in (2025, 2026):
            m.log_batch([{"name": "Salsa", "unit": "pints", "qty": y - 2020}], ingredients=[{"name": "T", "crop": "tomato", "lb": 1}], year=y)
        self.assertEqual([(i["year"], i["count"]) for i in m.snapshot()["pantry"]], [(2026, 6), (2025, 5)])


if __name__ == "__main__":
    unittest.main()


class ResourceRegistration(unittest.TestCase):
    def run_it(self, items, lovelace=None):
        import asyncio
        from resource import ensure_resource  # noqa
        class R:
            loaded = True
            def __init__(s): s.items = list(items)
            def async_items(s): return s.items
            async def async_create_item(s, d): s.items.append({"id": "n", **d})
            async def async_update_item(s, i, d):
                [x.update(d) for x in s.items if x["id"] == i]
        class L: resources = R()
        l = lovelace or L()
        out = asyncio.run(ensure_resource(l, "/put_em_up/c.js", "/put_em_up/c.js?v=2"))
        return out, l

    def test_adds_when_missing(self):
        out, l = self.run_it([])
        self.assertEqual(out, "added")
        self.assertEqual(l.resources.items[0]["res_type"], "module")

    def test_updates_a_hand_added_one_instead_of_duplicating(self):
        out, l = self.run_it([{"id": "1", "url": "/put_em_up/c.js", "res_type": "module"}])
        self.assertEqual(out, "updated")
        self.assertEqual(len(l.resources.items), 1)
        self.assertEqual(l.resources.items[0]["url"], "/put_em_up/c.js?v=2")

    def test_leaves_current_one_alone(self):
        out, _ = self.run_it([{"id": "1", "url": "/put_em_up/c.js?v=2", "res_type": "module"}])
        self.assertEqual(out, "unchanged")

    def test_yaml_mode_and_missing_lovelace(self):
        class L: resources = object()
        self.assertEqual(self.run_it([], L())[0], "yaml_mode")
        import asyncio
        from resource import ensure_resource  # noqa
        self.assertEqual(asyncio.run(ensure_resource(None, "a", "b")), "no_lovelace")
