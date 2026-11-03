"""Services. The card uses these too, so automations can do everything the card can."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .core.model import USE_KINDS, PantryError

R, O = vol.Required, vol.Optional
NUM = vol.Coerce(float)
ING = vol.Schema({R("name"): cv.string, O("crop"): vol.Any(None, cv.string), O("crop_name"): vol.Any(None, cv.string),
                  O("lb"): NUM, O("oz"): NUM})
PROD = vol.Schema({R("name"): cv.string, O("method"): cv.string, R("unit"): cv.string, R("qty"): NUM})

SERVICES: dict[str, tuple[dict, str]] = {
    "log_batch": ({R("products"): [PROD], O("ingredients"): [ING], O("recipe_id"): cv.string, O("multiplier"): NUM,
                   O("year"): cv.positive_int, O("date"): cv.date, O("notes"): cv.string}, "log_batch"),
    "delete_batch": ({R("batch_id"): cv.string}, "delete_batch"),
    "use_item": ({R("name"): cv.string, R("unit"): cv.string, R("year"): cv.positive_int, O("qty"): NUM, O("method"): cv.string,
                  O("kind"): vol.In(USE_KINDS), O("date"): cv.date}, "use_item"),
    "delete_use": ({R("use_id"): cv.string}, "delete_use"),
}


def async_register_services(hass: HomeAssistant) -> None:
    def make(method: str):
        async def handler(call: ServiceCall) -> None:
            mgr = hass.data.get(DOMAIN)
            if mgr is None:
                raise ServiceValidationError("Put 'Em Up is not set up")
            args = dict(call.data)
            if "date" in args:
                args["on"] = args.pop("date").isoformat()
            try:
                getattr(mgr, method)(**args)
            except PantryError as err:
                raise ServiceValidationError(str(err)) from err
        return handler

    for name, (schema, method) in SERVICES.items():
        hass.services.async_register(DOMAIN, name, make(method), schema=vol.Schema(schema))
