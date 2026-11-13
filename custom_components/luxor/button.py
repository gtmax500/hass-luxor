"""Controller-wide all-on / all-off buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LuxorConfigEntry, LuxorCoordinator
from .entity import LuxorEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LuxorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            LuxorAllButton(coordinator, "illuminate_all", "mdi:lightbulb-group"),
            LuxorAllButton(coordinator, "extinguish_all", "mdi:lightbulb-group-off"),
        ]
    )


class LuxorAllButton(LuxorEntity, ButtonEntity):
    def __init__(self, coordinator: LuxorCoordinator, key: str, icon: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_translation_key = key
        self._attr_icon = icon
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"

    async def async_press(self) -> None:
        if self._key == "illuminate_all":
            await self.coordinator.async_illuminate_all()
        else:
            await self.coordinator.async_extinguish_all()
