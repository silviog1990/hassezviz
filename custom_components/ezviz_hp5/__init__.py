"""EZVIZ HP5 Gate Controller integration.

Full setup (client lifecycle, platform forwarding) is added in a later
task. This minimal stub exists now only so `async_setup_entry` is a real
attribute on this module that the config flow's reauth-success path (and
tests exercising it) can call/patch.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EZVIZ HP5 Gate Controller from a config entry (stub)."""
    return True
