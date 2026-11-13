"""Single polling coordinator for a Luxor controller."""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import replace
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LuxorClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, REFRESH_COOLDOWN
from .protocol import LuxorError, LuxorState

_LOGGER = logging.getLogger(__name__)

type LuxorConfigEntry = ConfigEntry[LuxorCoordinator]


class LuxorCoordinator(DataUpdateCoordinator[LuxorState]):
    """Polls groups and themes together (two tiny requests per cycle).

    Commands update state optimistically so the UI reacts instantly, then a
    debounced refresh confirms what the controller actually did.
    """

    config_entry: LuxorConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: LuxorConfigEntry,
        client: LuxorClient,
        controller_name: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REFRESH_COOLDOWN, immediate=False
            ),
        )
        self.client = client
        self.controller_name = controller_name

    async def _async_update_data(self) -> LuxorState:
        try:
            return await self.client.get_state()
        except LuxorError as err:
            raise UpdateFailed(str(err)) from err

    async def _command(self, action: Awaitable[None]) -> None:
        try:
            await action
        except LuxorError as err:
            raise HomeAssistantError(f"Luxor controller: {err}") from err

    async def async_set_group(self, group_number: int, intensity: int) -> None:
        await self._command(self.client.illuminate_group(group_number, intensity))
        if (group := self.data.groups.get(group_number)) is not None:
            groups = dict(self.data.groups)
            groups[group_number] = replace(group, intensity=intensity)
            self.async_set_updated_data(replace(self.data, groups=groups))
        await self.async_request_refresh()

    async def async_set_theme(self, theme_index: int, on: bool) -> None:
        await self._command(self.client.illuminate_theme(theme_index, on))
        if (theme := self.data.themes.get(theme_index)) is not None:
            themes = dict(self.data.themes)
            themes[theme_index] = replace(theme, on=on)
            self.async_set_updated_data(replace(self.data, themes=themes))
        # A theme changes many groups at once; fetch the real levels.
        await self.async_request_refresh()

    async def async_illuminate_all(self) -> None:
        await self._command(self.client.illuminate_all())
        await self.async_request_refresh()

    async def async_extinguish_all(self) -> None:
        await self._command(self.client.extinguish_all())
        await self.async_request_refresh()
