"""Sensor platform for Triki."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ACCEL_LSB_PER_G, DOMAIN, GYRO_LSB_PER_DPS
from .coordinator import TrikiCoordinator, TrikiData
from .entity import TrikiEntity


@dataclass(frozen=True, kw_only=True)
class TrikiSensorDescription(SensorEntityDescription):
    """Describes one Triki sensor entity."""

    value_fn: Callable[[TrikiData], object]


SENSOR_DESCRIPTIONS: tuple[TrikiSensorDescription, ...] = (
    TrikiSensorDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.battery,
    ),
    TrikiSensorDescription(
        key="firmware",
        translation_key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.firmware,
    ),
    TrikiSensorDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.rssi,
    ),
)

# Accelerometer (g) / gyroscope (deg/s) axes, converted using the scale
# factors documented in Flopsstuff/triki (docs/guide/imu-streaming.md) and
# cross-checked against a real recorded session from this integration: the
# accel channel sat at ~2048-2110 raw (~1.00-1.03 g) on whichever axis was
# aligned with gravity while the token was still — consistent with the
# documented ACCEL_LSB_PER_G=2048 scale to within calibration noise.
# Disabled by default: at up to 416 Hz they are far too fast-changing to
# want in Home Assistant's recorder history by default — use the
# position/rotation binary sensors for automations instead.
AXIS_DESCRIPTIONS: tuple[TrikiSensorDescription, ...] = (
    TrikiSensorDescription(
        key="accel_x",
        translation_key="accel_x",
        native_unit_of_measurement="g",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.accel_x / ACCEL_LSB_PER_G,
    ),
    TrikiSensorDescription(
        key="accel_y",
        translation_key="accel_y",
        native_unit_of_measurement="g",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.accel_y / ACCEL_LSB_PER_G,
    ),
    TrikiSensorDescription(
        key="accel_z",
        translation_key="accel_z",
        native_unit_of_measurement="g",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.accel_z / ACCEL_LSB_PER_G,
    ),
    TrikiSensorDescription(
        key="gyro_x",
        translation_key="gyro_x",
        native_unit_of_measurement="°/s",
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.gyro_x / GYRO_LSB_PER_DPS,
    ),
    TrikiSensorDescription(
        key="gyro_y",
        translation_key="gyro_y",
        native_unit_of_measurement="°/s",
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.gyro_y / GYRO_LSB_PER_DPS,
    ),
    TrikiSensorDescription(
        key="gyro_z",
        translation_key="gyro_z",
        native_unit_of_measurement="°/s",
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.gyro_z / GYRO_LSB_PER_DPS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Triki sensors from a config entry."""
    coordinator: TrikiCoordinator = hass.data[DOMAIN][entry.entry_id]
    descriptions = SENSOR_DESCRIPTIONS + AXIS_DESCRIPTIONS
    async_add_entities(
        TrikiSensor(coordinator, description) for description in descriptions
    )


class TrikiSensor(TrikiEntity, SensorEntity):
    """A single Triki sensor value."""

    entity_description: TrikiSensorDescription

    def __init__(
        self, coordinator: TrikiCoordinator, description: TrikiSensorDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)
