"""Luxor themes as switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LuxorConfigEntry, LuxorCoordinator
from .entity import LuxorEntity
from .protocol import LuxorTheme

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LuxorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def _add_new_themes() -> None:
        new = [i for i in coordinator.data.themes if i not in known]
        if new:
            known.update(new)
            async_add_entities(LuxorThemeSwitch(coordinator, i) for i in new)

    _add_new_themes()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_themes))


class LuxorThemeSwitch(LuxorEntity, SwitchEntity):
    """On = IlluminateTheme(on), off = IlluminateTheme(off) (its groups to 0%).

    State is the controller's own OnOff flag, i.e. the last theme command.
    Adjusting a single group afterwards doesn't flip it.
    """

    _attr_icon = "mdi:palette-outline"

    def __init__(self, coordinator: LuxorCoordinator, theme_index: int) -> None:
        super().__init__(coordinator)
        self.theme_index = theme_index
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_theme_{theme_index}"

    @property
    def _theme(self) -> LuxorTheme | None:
        return self.coordinator.data.themes.get(self.theme_index)

    @property
    def available(self) -> bool:
        return super().available and self._theme is not None

    @property
    def name(self) -> str | None:
        theme = self._theme
        return f"Theme {theme.name}" if theme else f"Theme {self.theme_index}"

    @property
    def is_on(self) -> bool | None:
        theme = self._theme
        return None if theme is None else theme.on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"theme_index": self.theme_index}

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_theme(self.theme_index, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_theme(self.theme_index, False)
