"""Sensors: a count for each pantry item, plus 'left' and 'shortfall' pounds for each crop you've used."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_STRUCTURE, SIGNAL_UPDATE
from .core.model import OZ_PER_LB, slug
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
        self._attr_name = f"{item['name']} {item['year']}"
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
        return {"made": i.get("made"), "used": i.get("out"), "year": i.get("year")}


class CropSensor(_Base):
    """Pounds of one crop left, or short, this year."""
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_native_unit_of_measurement = UnitOfMass.POUNDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, mgr, known, key: str, name: str, field: str, label: str) -> None:
        super().__init__(mgr, known, f"crop_{field}_{key}", "garden_use", "Garden use", "Harvest used in batches")
        self._key, self._field = key, field
        self._attr_name = f"{name} {label}"

    @property
    def native_value(self):
        for c in self._mgr.snapshot()["crops"]:
            if c["key"] == self._key:
                row = c["years"].get(str(self._mgr.today().year))
                return round(row[self._field] / OZ_PER_LB, 2) if row else 0.0
        return 0.0

    @property
    def extra_state_attributes(self):
        for c in self._mgr.snapshot()["crops"]:
            if c["key"] == self._key:
                return {"by_year": {y: round(r[self._field] / OZ_PER_LB, 2) for y, r in c["years"].items()}}
        return {}


class ShortfallTotalSensor(_Base):
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_native_unit_of_measurement = UnitOfMass.POUNDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Total shortfall this year"

    def __init__(self, mgr, known) -> None:
        super().__init__(mgr, known, "shortfall_total", "garden_use", "Garden use", "Harvest used in batches")

    @property
    def native_value(self):
        return round(self._mgr.snapshot()["short_this_year_oz"] / OZ_PER_LB, 2)

    @property
    def extra_state_attributes(self):
        return {"by_year": {y: round(v / OZ_PER_LB, 2) for y, v in self._mgr.snapshot()["short_by_year"].items()}}


def _build(mgr: PantryManager, known: set) -> list:
    snap = mgr.snapshot()
    ents: list = []
    if "shortfall_total" not in known:
        ents.append(ShortfallTotalSensor(mgr, known))
    for item in snap["pantry"]:
        if f"pantry_{item['key']}" not in known:
            ents.append(PantrySensor(mgr, known, item))
    for c in snap["crops"]:
        for field, label in (("left_oz", "left this year"), ("short_oz", "shortfall this year")):
            if f"crop_{field}_{c['key']}" not in known:
                ents.append(CropSensor(mgr, known, c["key"], c["name"], field, label))
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
