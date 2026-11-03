# Put 'Em Up

A Home Assistant (HACS) integration for home food preservation: log what you canned, froze or freeze-dried, keep a pantry count that goes down as jars are eaten, and count what you used against your [Garden Tracker](https://github.com/stephencorrell-ops/Home-Garden-Tracker) harvest totals.

It is a **log**, not a recipe or canning-safety guide. For safe processing times and methods, use the [National Center for Home Food Preservation](https://nchfp.uga.edu/).

## What it does
- **Log a load:** pick the crop (from your Garden Tracker plants, or type any other), the date, the pounds in, and each product you made, such as 140 pints of salsa and 80 pints of diced tomatoes. Each product has a preservation method (canning, freeze drying, drying, freezing, pickling or fermenting) and a measurement (half-pints, pints, quarts, half-gallons or gallons). Choose Other… on either one to type your own, such as smoking or bags. It is remembered for next time. Log one canner load this weekend and another next weekend and they add together.
- **Yearly totals:** for each crop and year, the number of loads, total pounds in, and everything made, with jars per pound so you can compare years.
- **Pantry:** a count per item, method and year, so frozen peaches and canned peaches are counted separately. Tap to take one off when a jar is eaten, given away, or found.
- **Batches:** every batch with its pounds in and how many jars per pound it made.
- **Sensors:** a count for each pantry item, so you can put "Salsa: 96" on a dashboard or alert when something runs low.
- **Services:** `put_em_up.log_batch`, `use_item` and `delete_batch`, for automations.

It does not try to match recipe ingredients to your garden harvest. Pounds in is just what you entered, because trimming, peeling and seeding make garden weight and recipe weight differ.

If Garden Tracker (0.31.15 or later) is installed, the crop list comes from its "Harvest totals" sensors and the form shows how many pounds it logged for that crop. Without it, you type the crop name.

## Install
Add this repository to HACS as a custom repository (type: Integration), install **Put 'Em Up**, restart, then add the integration under Settings, Devices & services. Add the card to a dashboard:

```yaml
type: custom:put-em-up-card
```
