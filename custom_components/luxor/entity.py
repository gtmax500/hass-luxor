"""Base entity for Luxor."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import LuxorCoordinator


class LuxorEntity(CoordinatorEntity[LuxorCoordinator]):
    """All entities hang off one device: the controller."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LuxorCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            model="Luxor",
            name=coordinator.controller_name,
            configuration_url=coordinator.client.base_url,
        )
