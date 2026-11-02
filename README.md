# Put 'Em Up

A Home Assistant (HACS) integration for home food preservation: log what you canned, froze or freeze-dried, keep a pantry count that goes down as jars are eaten, and count what you used against your [Garden Tracker](https://github.com/stephencorrell-ops/Home-Garden-Tracker) harvest totals.

It is a **log**, not a recipe or canning-safety guide. For safe processing times and methods, use the [National Center for Home Food Preservation](https://nchfp.uga.edu/).

## What it does
- **Recipes:** enter ingredients once, in pounds and ounces, and what one batch makes (for example 7 pints of salsa). Ingredients can be tied to a garden crop.
- **Make a batch:** pick a recipe and a size (1×, 2×, 3×, or any number). Ingredient weights and expected jars scale up. Enter how many jars you actually got.
- **Pantry:** a count per item and year. Tap to take one off when a jar is eaten, given away, or found.
- **Garden use:** for each crop and year, what you harvested (from Garden Tracker), what batches used, what is left, and the **shortfall** if you used more than you grew (grew 40 lb of bell peppers, used 60: 20 lb short).
- **Sensors:** a count for each pantry item, pounds left and short for each crop this year, and a total shortfall for the year.
- **Services:** `put_em_up.log_batch`, `use_item`, `save_recipe` and more, for automations.

Garden totals are read from Garden Tracker's "Harvest totals" sensors (version 0.31.15 or later), so install that too if you want garden use counted. Without it, everything else works and garden items are simply counted as used.

## Install
Add this repository to HACS as a custom repository (type: Integration), install **Put 'Em Up**, restart, then add the integration under Settings, Devices & services. Add the card to a dashboard:

```yaml
type: custom:put-em-up-card
```
