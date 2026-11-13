"""Diagnostics download for Luxor (Settings > Devices > ... > Download diagnostics)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import LuxorConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LuxorConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return {
        "controller_name": coordinator.controller_name,
        "options": dict(entry.options),
        "last_update_success": coordinator.last_update_success,
        "state": asdict(coordinator.data) if coordinator.data else None,
    }
