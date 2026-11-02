"""Put 'Em Up: log canning and freeze-drying batches, track the pantry, and count what you use against your garden harvest."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from . import websocket
from .const import CARD_URL, DOMAIN, GARDEN_DOMAIN, SIGNAL_UPDATE, VERSION
from .manager import PantryManager
from .services import async_register_services

PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_register_services(hass)
    websocket.async_register(hass)
    card = Path(__file__).parent / "www" / "put-em-up-card.js"
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(card), False)])
    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    mgr = PantryManager(hass)
    await mgr.async_load()
    hass.data[DOMAIN] = mgr
    # Garden Tracker's totals change as harvests are logged; refresh the card and sensors when they do.
    from homeassistant.helpers.event import async_track_state_change_event
    from homeassistant.helpers import entity_registry as er

    def _watch() -> list[str]:
        return [e.entity_id for e in er.async_get(hass).entities.values()
                if e.platform == GARDEN_DOMAIN and "harvest_year_" in (e.unique_id or "")]

    def _on_garden(event) -> None:
        async_dispatcher_send(hass, SIGNAL_UPDATE)

    entry.async_on_unload(async_track_state_change_event(hass, _watch(), _on_garden))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        mgr: PantryManager = hass.data.pop(DOMAIN)
        await mgr.async_shutdown()
    return ok
