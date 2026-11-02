"""Add the card to the dashboard resource list. No Home Assistant imports, so it can be tested alone.

The companion app loads dashboard cards more reliably from the resource list than from the extra
script list, so the card is registered in both places.
"""
from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)


async def ensure_resource(lovelace, card_url: str, url: str) -> str:
    """Add or update the card in the dashboard resources. Returns what happened."""
    if lovelace is None:
        return "no_lovelace"
    resources = getattr(lovelace, "resources", None)
    if resources is None and isinstance(lovelace, dict):
        resources = lovelace.get("resources")
    if resources is None or not hasattr(resources, "async_create_item"):
        _LOGGER.debug("Dashboard resources are YAML-managed; add %s yourself", url)
        return "yaml_mode"
    if not getattr(resources, "loaded", True):
        await resources.async_load()
        resources.loaded = True
    for item in resources.async_items():
        if item.get("url", "").split("?")[0] == card_url:
            if item["url"] != url or item.get("res_type") != "module":
                await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
                return "updated"
            return "unchanged"
    await resources.async_create_item({"res_type": "module", "url": url})
    return "added"
