"""Climate platform for the Nilan Ventilation integration."""

from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NilanCoordinator
from .entity import NilanEntity

_MODE_TO_HVAC = {
    1: HVACMode.HEAT,
    2: HVACMode.COOL,
    3: HVACMode.AUTO,
}
_HVAC_TO_MODE = {
    HVACMode.HEAT: 1,
    HVACMode.COOL: 2,
    HVACMode.AUTO: 3,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NilanCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.register_climate(async_add_entities, _climate_entities)


def _climate_entities(coordinator: NilanCoordinator) -> list:
    if not coordinator.has_points("run_set", "mode_set", "vent_set"):
        return []
    if not (coordinator.has_points("temp_room") or coordinator.has_points("temp_control")):
        return []
    return [NilanClimate(coordinator)]


class NilanClimate(NilanEntity, ClimateEntity):
    """Operation mode and ventilation step of a CTS602 controller."""

    _attr_name = "Climate"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.FAN_MODE

    def __init__(self, coordinator: NilanCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_climate"
        self._vent_options = self._point_options("vent_set")
        self._attr_fan_modes = list(self._vent_options)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
        caps = self.coordinator.topology.caps if self.coordinator.topology else []
        if "cooling" in caps:
            modes.insert(2, HVACMode.COOL)
        return modes

    def _point_options(self, key: str) -> tuple[str, ...]:
        if self.coordinator.topology is None:
            return ()
        point = self.coordinator.topology.points.get(key)
        if point is None or not point.options:
            return ()
        return point.options

    @property
    def current_temperature(self) -> float | None:
        value = self.coordinator.value("temp_control")
        if value is None:
            value = self.coordinator.value("temp_room")
        return value

    @property
    def hvac_mode(self) -> HVACMode | None:
        run = self.coordinator.value("run_set")
        if run is None:
            return None
        if run < 1:
            return HVACMode.OFF
        mode = self.coordinator.value("mode_set")
        if mode is None:
            return None
        return _MODE_TO_HVAC.get(int(round(mode)))

    @property
    def fan_mode(self) -> str | None:
        value = self.coordinator.value("vent_set")
        if value is None or not self._vent_options:
            return None
        index = int(round(value))
        if 0 <= index < len(self._vent_options):
            return self._vent_options[index]
        return None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_write_point("run_set", 0.0)
            return
        mode = _HVAC_TO_MODE.get(hvac_mode)
        if mode is None:
            return
        await self.coordinator.async_write_point("run_set", 1.0)
        await self.coordinator.async_write_point("mode_set", float(mode))

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        options = self._vent_options
        if fan_mode in options:
            await self.coordinator.async_write_point("vent_set", float(options.index(fan_mode)))
            return
        try:
            value = float(fan_mode)
        except (TypeError, ValueError):
            return
        await self.coordinator.async_write_point("vent_set", value)
