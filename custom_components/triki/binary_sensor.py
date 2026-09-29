"""Binary sensor platform for Triki."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TrikiCoordinator, TrikiData
from .entity import TrikiEntity


@dataclass(frozen=True, kw_only=True)
class TrikiBinarySensorDescription(BinarySensorEntityDescription):
    """Describes one Triki binary sensor entity."""

    value_fn: Callable[[TrikiData], bool]


# Position: derived from the accelerometer, only asserted while the token is
# resting close to 1 g on a single dominant axis (see coordinator.py
# _update_derived). Confirmed against a real recorded session: the token
# sat pos_up ~84% of the time, pos_down ~6.5%, briefly pos_vertical/
# pos_side_* during handling — see the chat for the full breakdown.
POSITION_DESCRIPTIONS: tuple[TrikiBinarySensorDescription, ...] = (
    TrikiBinarySensorDescription(
        key="pos_up",
        translation_key="pos_up",
        value_fn=lambda data: data.pos_up,
    ),
    TrikiBinarySensorDescription(
        key="pos_down",
        translation_key="pos_down",
        value_fn=lambda data: data.pos_down,
    ),
    TrikiBinarySensorDescription(
        key="pos_horizontal",
        translation_key="pos_horizontal",
        value_fn=lambda data: data.pos_horizontal,
    ),
    TrikiBinarySensorDescription(
        key="pos_vertical",
        translation_key="pos_vertical",
        value_fn=lambda data: data.pos_vertical,
    ),
    # Bonus / "other useful orientations": on-its-side detection. Which
    # physical side is "left" vs "right" is NOT independently verified
    # (depends on how the PCB is mounted inside the cap) — flip the two
    # value_fn's below if they come out backwards on your unit.
    TrikiBinarySensorDescription(
        key="pos_side_left",
        translation_key="pos_side_left",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.pos_side_left,
    ),
    TrikiBinarySensorDescription(
        key="pos_side_right",
        translation_key="pos_side_right",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.pos_side_right,
    ),
)

# Rotation: derived from gyro Z (yaw). Sign -> direction is likewise not
# independently verified against a physical "clockwise seen from above"
# reference — flip if backwards on your unit.
ROTATION_DESCRIPTIONS: tuple[TrikiBinarySensorDescription, ...] = (
    TrikiBinarySensorDescription(
        key="rotating_right",
        translation_key="rotating_right",
        value_fn=lambda data: data.rotating_right,
    ),
    TrikiBinarySensorDescription(
        key="rotating_left",
        translation_key="rotating_left",
        value_fn=lambda data: data.rotating_left,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Triki binary sensors from a config entry."""
    coordinator: TrikiCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = [
        TrikiButtonSensor(coordinator),
        TrikiConnectivitySensor(coordinator),
    ]
    entities.extend(
        TrikiDerivedBinarySensor(coordinator, description)
        for description in POSITION_DESCRIPTIONS + ROTATION_DESCRIPTIONS
    )
    async_add_entities(entities)


class TrikiButtonSensor(TrikiEntity, BinarySensorEntity):
    """Whether the cap's physical button is currently pressed."""

    _attr_translation_key = "button"

    def __init__(self, coordinator: TrikiCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_button"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.button_pressed


class TrikiConnectivitySensor(TrikiEntity, BinarySensorEntity):
    """Whether Home Assistant currently has an active BLE connection."""

    _attr_translation_key = "connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TrikiCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_connectivity"

    @property
    def available(self) -> bool:
        # This entity reports connectivity itself, so it stays available
        # even while the device is disconnected.
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.available


class TrikiDerivedBinarySensor(TrikiEntity, BinarySensorEntity):
    """A position/rotation flag computed from the raw accel+gyro stream."""

    entity_description: TrikiBinarySensorDescription

    def __init__(
        self, coordinator: TrikiCoordinator, description: TrikiBinarySensorDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator.data)
