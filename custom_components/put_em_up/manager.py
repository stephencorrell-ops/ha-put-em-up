"""Home Assistant wrapper around the pure pantry model."""
from __future__ import annotations

import re

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import GARDEN_DOMAIN, SIGNAL_STRUCTURE, SIGNAL_UPDATE, STORAGE_KEY, STORAGE_VERSION
from .core.model import PantryModel


class PantryManager(PantryModel):
    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__({}, lambda: dt_util.now().date(), self._on_change, self._on_structure)
        self.hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.garden = self.garden_totals

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.data = data
        for k in ("recipes", "batches", "uses"):
            self.data.setdefault(k, {})

    def garden_totals(self) -> dict:
        """Yearly pounds per plant type, read from Garden Tracker's 'harvest totals' sensors."""
        out: dict[str, dict] = {}
        reg = er.async_get(self.hass)
        for ent in reg.entities.values():
            if ent.platform != GARDEN_DOMAIN or "harvest_year_" not in (ent.unique_id or ""):
                continue
            key = ent.unique_id.split("harvest_year_", 1)[1]
            if key == "all":
                continue
            state = self.hass.states.get(ent.entity_id)
            if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                continue
            by_year = state.attributes.get("by_year") or {}
            name = ent.name or ent.original_name or state.name or key
            name = re.sub(r"\s+this year$", "", name, flags=re.I)
            out[key] = {"name": name, "years": {str(y): float(v) for y, v in by_year.items()}}
        return out

    def _on_change(self) -> None:
        self._save()
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    def _on_structure(self) -> None:
        self._save()
        async_dispatcher_send(self.hass, SIGNAL_STRUCTURE)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    def _save(self) -> None:
        self._store.async_delay_save(lambda: self.data, 1)

    async def async_shutdown(self) -> None:
        await self._store.async_save(self.data)
