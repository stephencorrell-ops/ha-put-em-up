"""Sensors: a count for each pantry item."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_STRUCTURE, SIGNAL_UPDATE
from .core.model import method_label
from .manager import PantryManager


class _Base(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, mgr: PantryManager, known: set, uid: str, ident: str, device: str, model: str) -> None:
        self._mgr, self._known = mgr, known
        self._attr_unique_id = uid
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, ident)}, name=device, model=model, manufacturer="Put 'Em Up")
        known.add(uid)

    async def async_added_to_hass(self) -> None:
        @callback
        def _upd() -> None:
            self.async_write_ha_state()
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_UPDATE, _upd))

    async def async_will_remove_from_hass(self) -> None:
        self._known.discard(self._attr_unique_id)


class PantrySensor(_Base):
    _attr_icon = "mdi:jar"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, mgr, known, item: dict) -> None:
        super().__init__(mgr, known, f"pantry_{item['key']}", "pantry", "Pantry", "Home-preserved food")
        self._key = item["key"]
        self._attr_name = f"{item['name']} ({method_label(item['method'])}) {item['year']}"
        self._attr_native_unit_of_measurement = item["unit"]

    def _item(self):
        return next((i for i in self._mgr.snapshot()["pantry"] if i["key"] == self._key), None)

    @property
    def available(self) -> bool:
        return self._item() is not None

    @property
    def native_value(self):
        i = self._item()
        return i["count"] if i else None

    @property
    def extra_state_attributes(self):
        i = self._item() or {}
        return {"made": i.get("made"), "used": i.get("out"), "year": i.get("year"), "method": i.get("method")}


def _build(mgr: PantryManager, known: set) -> list:
    snap = mgr.snapshot()
    ents: list = []
    for item in snap["pantry"]:
        if f"pantry_{item['key']}" not in known:
            ents.append(PantrySensor(mgr, known, item))
    return ents


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    mgr: PantryManager = hass.data[DOMAIN]
    known: set[str] = set()
    async_add_entities(_build(mgr, known))

    @callback
    def _grow() -> None:
        new = _build(mgr, known)
        if new:
            async_add_entities(new)

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_STRUCTURE, _grow))
