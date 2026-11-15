"""Binary sensor platform for the Nilan Ventilation integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KIND_BINARY
from .coordinator import NilanCoordinator
from .entity import NilanEntity, NilanPointEntity
from .models import NilanPoint


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NilanCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NilanOnlineBinarySensor(coordinator)])
    coordinator.register_platform("binary_sensor", async_add_entities, _point_binary_sensors)


def _point_binary_sensors(coordinator: NilanCoordinator, point: NilanPoint) -> list:
    if point.kind != KIND_BINARY:
        return []
    return [NilanBinarySensor(coordinator, point)]


class NilanBinarySensor(NilanPointEntity, BinarySensorEntity):
    """A read-only boolean point."""

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.values.get(self.point.key)
        if value is None:
            return None
        return value >= 1


class NilanOnlineBinarySensor(NilanEntity, BinarySensorEntity):
    """Whether the ventilation controller answers Modbus polls."""

    _attr_name = "Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: NilanCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_online"

    @property
    def available(self) -> bool:
        return CoordinatorEntity.available.fget(self)  # type: ignore[attr-defined]

    @property
    def is_on(self) -> bool:
        return self.coordinator.online
