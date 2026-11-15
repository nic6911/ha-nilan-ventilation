"""Select platform for the Nilan Ventilation integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KIND_SELECT
from .coordinator import NilanCoordinator
from .entity import NilanPointEntity
from .models import NilanPoint


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NilanCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.register_platform("select", async_add_entities, _point_selects)


def _point_selects(coordinator: NilanCoordinator, point: NilanPoint) -> list:
    if point.kind != KIND_SELECT or not point.writable or not point.options:
        return []
    return [NilanSelect(coordinator, point)]


class NilanSelect(NilanPointEntity, SelectEntity):
    """A writable enumerated holding register."""

    def __init__(self, coordinator: NilanCoordinator, point: NilanPoint) -> None:
        super().__init__(coordinator, point)
        self._attr_options = list(point.options or ())

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.values.get(self.point.key)
        if value is None or not self._attr_options:
            return None
        index = int(round(value))
        if 0 <= index < len(self._attr_options):
            return self._attr_options[index]
        return None

    async def async_select_option(self, option: str) -> None:
        options = self._attr_options
        if option not in options:
            return
        await self.coordinator.async_write_point(self.point.key, float(options.index(option)))
