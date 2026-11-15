"""Sensor platform for the Nilan Ventilation integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KIND_SENSOR
from .coordinator import NilanCoordinator
from .entity import NilanEntity, NilanPointEntity
from .models import NilanPoint

_UNIT_MAP: dict[str, tuple[str, SensorDeviceClass | None]] = {
    "\u00b0C": (UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "ppm": (CONCENTRATION_PARTS_PER_MILLION, None),
    "Pa": (UnitOfPressure.PA, SensorDeviceClass.PRESSURE),
    "m3/h": (UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR, SensorDeviceClass.VOLUME_FLOW_RATE),
    "s": (UnitOfTime.SECONDS, SensorDeviceClass.DURATION),
    "min": (UnitOfTime.MINUTES, SensorDeviceClass.DURATION),
    "h": (UnitOfTime.HOURS, SensorDeviceClass.DURATION),
    "days": (UnitOfTime.DAYS, SensorDeviceClass.DURATION),
    "kWh": (UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY),
    "V": (UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE),
    "A": (UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT),
    "Hz": (UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY),
    "W": (UnitOfPower.WATT, SensorDeviceClass.POWER),
}

_STATUS_SENSORS: tuple[tuple[str, str, str | None, SensorDeviceClass | None], ...] = (
    ("poll_ms", "Poll duration", UnitOfTime.MILLISECONDS, SensorDeviceClass.DURATION),
    ("polls", "Poll cycles", None, None),
    ("failures", "Modbus failures", None, None),
    ("retries", "Modbus retries", None, None),
    ("timeouts", "Modbus timeouts", None, None),
    ("crc_errors", "CRC errors", None, None),
    ("exceptions", "Modbus exceptions", None, None),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NilanCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(NilanStatusSensor(coordinator, *meta) for meta in _STATUS_SENSORS)
    coordinator.register_platform("sensor", async_add_entities, _point_sensors)


def _point_sensors(coordinator: NilanCoordinator, point: NilanPoint) -> list:
    if point.kind != KIND_SENSOR:
        return []
    return [NilanSensor(coordinator, point)]


class NilanSensor(NilanPointEntity, SensorEntity):
    """A read-only numeric or enumerated sensor."""

    def __init__(self, coordinator: NilanCoordinator, point: NilanPoint) -> None:
        super().__init__(coordinator, point)
        if point.options is None:
            unit, device_class = _sensor_meta(point.unit, point.key)
            if unit is not None:
                self._attr_native_unit_of_measurement = unit
            if device_class is not None:
                self._attr_device_class = device_class
            self._attr_state_class = SensorStateClass.MEASUREMENT
            if point.scale < 0:
                self._attr_suggested_display_precision = -point.scale

    @property
    def native_value(self) -> float | str | None:
        value = self.coordinator.values.get(self.point.key)
        if value is None:
            return None
        options = self.point.options
        if options:
            index = int(round(value))
            if 0 <= index < len(options):
                return options[index]
            return str(index)
        return value


def _sensor_meta(
    unit: str | None, key: str
) -> tuple[str | None, SensorDeviceClass | None]:
    if unit is None:
        return None, None
    if unit == "%":
        if key in ("rh", "rh_average", "humidity"):
            return PERCENTAGE, SensorDeviceClass.HUMIDITY
        return PERCENTAGE, None
    if unit == "ppm" and key in ("co2", "co2_room"):
        return CONCENTRATION_PARTS_PER_MILLION, SensorDeviceClass.CO2
    if unit == "ppm" and key == "voc":
        return (
            CONCENTRATION_PARTS_PER_MILLION,
            SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        )
    return _UNIT_MAP.get(unit, (unit, None))


class NilanStatusSensor(NilanEntity, SensorEntity):
    """A diagnostic sensor backed by the status JSON payload."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: NilanCoordinator,
        key: str,
        name: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
    ) -> None:
        super().__init__(coordinator)
        self._status_key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.mac}_status_{key}"
        if unit is not None:
            self._attr_native_unit_of_measurement = unit
        if device_class is not None:
            self._attr_device_class = device_class
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> Any:
        value = self.coordinator.status.get(self._status_key)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return value
        return None
