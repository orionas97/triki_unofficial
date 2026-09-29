"""Shared base entity for Triki platforms."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import TrikiCoordinator


class TrikiEntity(CoordinatorEntity[TrikiCoordinator]):
    """Base class providing shared device_info / availability for all platforms."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TrikiCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={("bluetooth", coordinator.address)},
            name=coordinator.device_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=coordinator.data.firmware,
        )

    @property
    def available(self) -> bool:
        """Entities are unavailable while the BLE connection is down."""
        return super().available and self.coordinator.data.available
