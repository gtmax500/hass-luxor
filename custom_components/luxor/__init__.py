"""FX Luminaire Luxor integration (local JSON API)."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LuxorClient
from .const import DEFAULT_SCAN_INTERVAL, MAX_SCAN_INTERVAL, MIN_SCAN_INTERVAL
from .coordinator import LuxorConfigEntry, LuxorCoordinator
from .protocol import LuxorError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.LIGHT, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: LuxorConfigEntry) -> bool:
    client = LuxorClient(async_get_clientsession(hass), entry.data[CONF_HOST])
    try:
        controller_name = await client.controller_name()
    except LuxorError as err:
        raise ConfigEntryNotReady(f"Cannot reach Luxor at {client.host}: {err}") from err

    coordinator = LuxorCoordinator(hass, entry, client, controller_name)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LuxorConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: LuxorConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: LuxorConfigEntry) -> bool:
    """Migrate entries created by the original dcramer/hass-luxor (v1)."""
    if entry.version > 2:
        return False

    if entry.version == 1:
        old = dict(entry.data)
        interval = int(old.get("group_interval", DEFAULT_SCAN_INTERVAL))
        interval = max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, interval))

        @callback
        def _migrate_unique_id(reg_entry: er.RegistryEntry) -> dict[str, str] | None:
            # v1 lights were "LUXOR_LIGHT_<n>". v1 theme scenes become
            # switches, so those can't carry over; delete them by hand.
            if reg_entry.unique_id.startswith("LUXOR_LIGHT_"):
                number = reg_entry.unique_id.removeprefix("LUXOR_LIGHT_")
                return {"new_unique_id": f"{entry.entry_id}_group_{number}"}
            return None

        await er.async_migrate_entries(hass, entry.entry_id, _migrate_unique_id)
        hass.config_entries.async_update_entry(
            entry,
            data={CONF_HOST: old[CONF_HOST]},
            options={CONF_SCAN_INTERVAL: interval},
            version=2,
        )
        _LOGGER.info("Migrated Luxor config entry %s to version 2", entry.entry_id)

    return True
