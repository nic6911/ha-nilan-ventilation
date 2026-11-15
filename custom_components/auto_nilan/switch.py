"""Switch platform for the Nilan Ventilation integration."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KIND_SWITCH
from .coordinator import NilanCoordinator
from .entity import NilanPointEntity
from .models import NilanPoint


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NilanCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.register_platform("switch", async_add_entities, _point_switches)


def _point_switches(coordinator: NilanCoordinator, point: NilanPoint) -> list:
    if point.kind != KIND_SWITCH or not point.writable:
        return []
    return [NilanSwitch(coordinator, point)]


class NilanSwitch(NilanPointEntity, SwitchEntity):
    """A writable boolean holding register."""

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.values.get(self.point.key)
        if value is None:
            return None
        return value >= 1

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write_point(self.point.key, 1.0)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write_point(self.point.key, 0.0)
