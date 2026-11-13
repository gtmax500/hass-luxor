"""Luxor groups as dimmable lights."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_ON_INTENSITY
from .coordinator import LuxorConfigEntry, LuxorCoordinator
from .entity import LuxorEntity
from .protocol import LuxorGroup, brightness_to_intensity, intensity_to_brightness

PARALLEL_UPDATES = 0  # the client serializes requests itself


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LuxorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def _add_new_groups() -> None:
        new = [n for n in coordinator.data.groups if n not in known]
        if new:
            known.update(new)
            async_add_entities(LuxorGroupLight(coordinator, n) for n in new)

    _add_new_groups()
    # Groups added later in the Luxor app show up without a reload.
    entry.async_on_unload(coordinator.async_add_listener(_add_new_groups))


class LuxorGroupLight(LuxorEntity, LightEntity):
    """One Luxor group (every fixture assigned to that group number)."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, coordinator: LuxorCoordinator, group_number: int) -> None:
        super().__init__(coordinator)
        self.group_number = group_number
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_group_{group_number}"
        self._last_on_intensity = DEFAULT_ON_INTENSITY
        self._remember_level()

    @property
    def _group(self) -> LuxorGroup | None:
        return self.coordinator.data.groups.get(self.group_number)

    def _remember_level(self) -> None:
        if (group := self._group) is not None and group.intensity > 0:
            self._last_on_intensity = group.intensity

    @callback
    def _handle_coordinator_update(self) -> None:
        self._remember_level()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        return super().available and self._group is not None

    @property
    def name(self) -> str | None:
        group = self._group
        return group.name if group else f"Group {self.group_number}"

    @property
    def is_on(self) -> bool | None:
        group = self._group
        return None if group is None else group.intensity > 0

    @property
    def brightness(self) -> int | None:
        group = self._group
        if group is None or group.intensity == 0:
            return None
        return intensity_to_brightness(group.intensity)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        group = self._group
        attrs: dict[str, Any] = {"group_number": self.group_number}
        if group is not None:
            attrs["intensity"] = group.intensity
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            intensity = brightness_to_intensity(kwargs[ATTR_BRIGHTNESS])
        else:
            # Plain "on" restores the last level instead of jumping to 100%.
            intensity = self._last_on_intensity
        await self.coordinator.async_set_group(self.group_number, intensity)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_group(self.group_number, 0)
