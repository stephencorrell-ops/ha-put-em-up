"""Websocket API used by the Lovelace card."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_UPDATE


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    mgr = hass.data.get(DOMAIN)
    if mgr is None:
        connection.send_error(msg["id"], "not_ready", "Put 'Em Up is not set up")
        return

    @callback
    def _push() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], mgr.snapshot()))

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(hass, SIGNAL_UPDATE, _push)
    connection.send_result(msg["id"])
    _push()


def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_subscribe)
