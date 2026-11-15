"""Base entities for the Nilan Ventilation integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NilanCoordinator
from .models import NilanPoint


class NilanEntity(CoordinatorEntity[NilanCoordinator]):
    """Base class for an entity belonging to the Nilan unit."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NilanCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        return self.coordinator.parent_device_info()

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.online


class NilanPointEntity(NilanEntity):
    """Base class for an entity backed by one catalog point."""

    def __init__(self, coordinator: NilanCoordinator, point: NilanPoint) -> None:
        super().__init__(coordinator)
        self.point = point
        self._attr_name = point.name
        self._attr_unique_id = f"{coordinator.mac}_{point.key}"
        if point.diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if point.disabled:
            self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> float | None:
        return self.coordinator.values.get(self.point.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "nilan_key": self.point.key,
            "register": f"{self.point.reg}:{self.point.addr}",
            "scale": self.point.scale,
            "capability": self.point.cap,
        }
