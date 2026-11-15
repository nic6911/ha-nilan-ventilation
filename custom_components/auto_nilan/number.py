"""Number platform for the Nilan Ventilation integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KIND_NUMBER
from .coordinator import NilanCoordinator
from .entity import NilanPointEntity
from .models import NilanPoint

_NUMBER_UNITS = {
    "\u00b0C": "\u00b0C",
    "%": "%",
    "ppm": "ppm",
    "Pa": "Pa",
    "m3/h": "m3/h",
    "s": "s",
    "min": "min",
    "h": "h",
    "days": "days",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NilanCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.register_platform("number", async_add_entities, _point_numbers)


def _point_numbers(coordinator: NilanCoordinator, point: NilanPoint) -> list:
    if point.kind != KIND_NUMBER or not point.writable:
        return []
    return [NilanNumber(coordinator, point)]


class NilanNumber(NilanPointEntity, NumberEntity):
    """A writable numeric holding register."""

    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: NilanCoordinator, point: NilanPoint) -> None:
        super().__init__(coordinator, point)
        self._attr_native_min_value = float(point.min_value if point.min_value is not None else 0)
        self._attr_native_max_value = float(point.max_value if point.max_value is not None else 100)
        self._attr_native_step = point.step
        if point.scale < 0:
            self._attr_suggested_display_precision = -point.scale
        if point.unit:
            self._attr_native_unit_of_measurement = _NUMBER_UNITS.get(point.unit, point.unit)

    @property
    def native_value(self) -> float | None:
        return self.coordinator.values.get(self.point.key)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write_point(self.point.key, value)
