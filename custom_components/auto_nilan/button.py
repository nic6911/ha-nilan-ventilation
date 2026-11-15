"""Button platform for the Nilan Ventilation integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KIND_BUTTON
from .coordinator import NilanCoordinator
from .entity import NilanEntity, NilanPointEntity
from .models import NilanPoint


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NilanCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NilanActionButton(
                coordinator, "commission", "Commission", coordinator.async_commission
            ),
            NilanActionButton(
                coordinator, "reset_alarm", "Alarm reset", coordinator.async_reset_alarm
            ),
        ]
    )
    coordinator.register_platform("button", async_add_entities, _point_buttons)


def _point_buttons(coordinator: NilanCoordinator, point: NilanPoint) -> list:
    if point.kind != KIND_BUTTON or not point.writable:
        return []
    return [NilanButton(coordinator, point)]


class NilanButton(NilanPointEntity, ButtonEntity):
    """A command register that is triggered by writing its maximum value."""

    async def async_press(self) -> None:
        await self.coordinator.async_press_point(self.point.key)


class NilanActionButton(NilanEntity, ButtonEntity):
    """A component-level action such as commissioning."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: NilanCoordinator,
        key: str,
        name: str,
        action: Callable[[], Awaitable[None]],
    ) -> None:
        super().__init__(coordinator)
        self._action = action
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.mac}_action_{key}"

    async def async_press(self) -> None:
        await self._action()

    @property
    def available(self) -> bool:
        """Available as long as the ESPHome connection is up."""
        return CoordinatorEntity.available.fget(self)  # type: ignore[attr-defined]
