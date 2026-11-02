import sys, unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "put_em_up"))
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
