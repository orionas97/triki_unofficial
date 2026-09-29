"""Switch platform for Triki (green LED control)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TrikiCoordinator
from .entity import TrikiEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Triki LED switch from a config entry."""
    coordinator: TrikiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TrikiLedSwitch(coordinator)])


class TrikiLedSwitch(TrikiEntity, SwitchEntity):
    """Controls the controller's built-in green LED."""

    _attr_translation_key = "led"
    _attr_icon = "mdi:led-on"

    def __init__(self, coordinator: TrikiCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_led"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.led_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_led(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_led(False)
