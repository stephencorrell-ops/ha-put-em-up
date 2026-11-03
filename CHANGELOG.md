# Changelog

After updating in HACS, restart Home Assistant and refresh your dashboard (close and reopen the app on a phone or tablet) so the new card loads.

## 0.2.0

Simplified to a plain log. Recipes, ingredient weights, garden use and shortfall are gone: garden weight and recipe weight can't be matched reliably once you trim, peel and seed. A batch is now a crop, the pounds in, and what you made. The form still shows what Garden Tracker logged for that crop as a reference.

## 0.1.3

The dashboard resource address stays plain (no ?v= number). A changing address stopped the card from loading in the Home Assistant app.

## 0.1.2

The card is now added to your dashboard resources automatically, which the Home Assistant app needs to show it. The card's address changes whenever the file does, so the app picks up new versions.

## 0.1.1

Fixed the card not loading next to another custom card that uses the same names ("Custom element doesn't exist: put-em-up-card").

## 0.1.0
First version: recipes, batch sizes, pantry counts, garden use with shortfall, sensors and services.
