"""ESPHome native API coordinator for a Nilan ventilation unit."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import inspect
import logging
from typing import Any

from aioesphomeapi import (
    APIClient,
    ConnectionClosedEvent,
    TextSensorInfo,
    TextSensorState,
    UserService,
)

try:  # pragma: no cover - kept for older aioesphomeapi releases
    from aioesphomeapi.core import ConnectionNotEstablishedAPIError
except ImportError:  # pragma: no cover
    ConnectionNotEstablishedAPIError = Exception  # type: ignore[misc,assignment]

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_NOISE_PSK,
    CONF_PASSWORD,
    DOMAIN,
    MANUFACTURER,
    TEXT_SENSOR_SUFFIXES,
    TEXT_STATUS,
    TEXT_TOPOLOGY,
    TEXT_VALUES,
)
from .models import NilanPoint, NilanTopology, parse_status, parse_topology, parse_values

_LOGGER = logging.getLogger(__name__)

PointEntityFactory = Callable[["NilanCoordinator", NilanPoint], list[Entity]]
ClimateEntityFactory = Callable[["NilanCoordinator"], list[Entity]]


class NilanCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Own the ESPHome native API connection and the Nilan point catalog."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.entry = entry
        self.client = APIClient(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data.get(CONF_PASSWORD) or None,
            noise_psk=entry.data.get(CONF_NOISE_PSK) or None,
            client_info="ha-auto-nilan",
        )
        self.mac: str = ""
        self.device_name: str = ""
        self.sw_version: str | None = None

        self.topology: NilanTopology | None = None
        self.values: dict[str, float] = {}
        self.status: dict[str, Any] = {}
        self.online = False
        self.services: dict[str, UserService] = {}
        self._text_keys: dict[int, str] = {}
        self._subscribed = False

        self._platforms: dict[str, tuple[Callable, PointEntityFactory]] = {}
        self._platform_entities: dict[str, dict[str, list[Entity]]] = {}
        self._climate_factory: ClimateEntityFactory | None = None
        self._climate_add_entities: Callable | None = None
        self._climate_added = False

        self._reconnect_task: asyncio.Task | None = None
        self._connect_lock = asyncio.Lock()
        self._shutdown = False
        self._remove_connection_closed = self.client.add_connection_closed_callback(
            self._on_connection_closed
        )

    async def async_setup(self) -> None:
        await self._async_connect_and_discover()

    async def _async_connect_and_discover(self) -> None:
        async with self._connect_lock:
            await self._async_connect_and_discover_locked()

    async def _async_connect_and_discover_locked(self) -> None:
        if not self.client.is_connected:
            connect_kwargs: dict[str, Any] = {"login": True}
            try:
                params = inspect.signature(self.client.connect).parameters
            except (TypeError, ValueError):  # pragma: no cover - exotic builds
                params = {}
            if "on_stop" in params:
                connect_kwargs["on_stop"] = self._on_stop
            await self.client.connect(**connect_kwargs)
        device_info = self.client.device_info
        if callable(device_info):
            device_info = await device_info()
        if device_info is None:
            raise RuntimeError("ESPHome device information is unavailable")
        self.mac = device_info.mac_address
        self.device_name = device_info.name
        self.sw_version = device_info.project_version or device_info.esphome_version

        entities, services = await self.client.list_entities_services()
        self.services = {service.name: service for service in services}

        text_keys: dict[int, str] = {}
        for info in entities:
            if not isinstance(info, TextSensorInfo):
                continue
            kind = self.classify_text_sensor(info)
            if kind is not None:
                text_keys[info.key] = kind
        missing = [kind for kind in TEXT_SENSOR_SUFFIXES if kind not in text_keys.values()]
        if TEXT_TOPOLOGY in missing or TEXT_VALUES in missing:
            raise RuntimeError(f"Missing Nilan text sensors: {', '.join(missing)}")
        self._text_keys = text_keys
        if not self._subscribed:
            self.client.subscribe_states(self._on_state)
            self._subscribed = True
        self._async_register_device()

    @staticmethod
    def classify_text_sensor(info: TextSensorInfo) -> str | None:
        object_id = (info.object_id or "").lower()
        name = (info.name or "").lower()
        for kind, suffix in TEXT_SENSOR_SUFFIXES.items():
            short = suffix[1:]
            if object_id.endswith(suffix) or object_id == short:
                return kind
            if name.endswith(short) or name.endswith(short.replace("_", " ")):
                return kind
        return None

    @callback
    def _async_register_device(self) -> None:
        if not self.mac:
            return
        dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id,
            identifiers={(DOMAIN, self.mac)},
            name=self.device_name,
            manufacturer=MANUFACTURER,
            model=self._model_name(),
            sw_version=self.sw_version,
        )

    def _model_name(self) -> str:
        if self.topology is not None and self.topology.model_name:
            return self.topology.model_name
        return "Ventilation unit"

    def parent_device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.mac)},
            name=self.device_name,
            manufacturer=MANUFACTURER,
            model=self._model_name(),
            sw_version=self.sw_version,
        )

    async def _async_update_data(self) -> dict[str, float]:
        if not self.client.is_connected:
            try:
                await self._async_connect_and_discover()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Reconnect failed: %s", err)
                self.online = False
        return self.values

    async def async_shutdown(self) -> None:
        self._shutdown = True
        self._remove_connection_closed()
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        await self.client.disconnect()

    @callback
    def _on_connection_closed(self, event: ConnectionClosedEvent) -> None:
        if self._shutdown:
            return
        self._subscribed = False
        self.online = False
        self.async_set_updated_data(self.values)
        _LOGGER.warning("ESPHome connection closed (%s); scheduling reconnect", event)
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = self.hass.async_create_task(self._async_reconnect())

    async def _on_stop(self, expected: bool) -> None:
        if self._shutdown:
            return
        self._subscribed = False
        self.online = False
        self.async_set_updated_data(self.values)
        _LOGGER.warning("ESPHome connection stopped; reconnecting")
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = self.hass.async_create_task(self._async_reconnect())

    async def _async_reconnect(self) -> None:
        while not self._shutdown:
            try:
                await asyncio.sleep(3)
                await self._async_connect_and_discover()
                _LOGGER.info("Reconnected to Nilan ESPHome device")
                return
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Reconnect failed: %s", err)
                await asyncio.sleep(5)

    @callback
    def _on_state(self, state: TextSensorState) -> None:
        kind = self._text_keys.get(state.key)
        if kind is None or getattr(state, "missing_state", False):
            return
        payload = getattr(state, "state", None)
        if not payload:
            return
        if kind == TEXT_TOPOLOGY:
            self._handle_topology(payload)
        elif kind == TEXT_VALUES:
            self._handle_values(payload)
        elif kind == TEXT_STATUS:
            self._handle_status(payload)

    @callback
    def _handle_topology(self, payload: str) -> None:
        try:
            topology = parse_topology(payload)
        except (TypeError, ValueError, KeyError) as err:
            _LOGGER.warning("Invalid Nilan topology JSON: %s", err)
            return
        if topology.version != 1:
            _LOGGER.warning("Unsupported Nilan topology version: %s", topology.version)
        _LOGGER.info(
            "Nilan %s (%s): %s points, capabilities %s",
            topology.profile,
            topology.model_name,
            len(topology.points),
            ", ".join(topology.caps) or "none",
        )
        self.topology = topology
        self._async_register_device()
        self.async_set_updated_data(self.values)
        self._sync_all_platforms()

    @callback
    def _handle_values(self, payload: str) -> None:
        try:
            values, online = parse_values(payload)
        except (TypeError, ValueError, KeyError) as err:
            _LOGGER.warning("Invalid Nilan values JSON: %s", err)
            return
        self.values = values
        self.online = online
        self.async_set_updated_data(self.values)

    @callback
    def _handle_status(self, payload: str) -> None:
        try:
            status = parse_status(payload)
        except (TypeError, ValueError) as err:
            _LOGGER.warning("Invalid Nilan status JSON: %s", err)
            return
        self.status = status
        self.online = bool(status.get("online", self.online))
        self.async_set_updated_data(self.values)

    def register_platform(
        self, key: str, add_entities: Callable, factory: PointEntityFactory
    ) -> None:
        self._platforms[key] = (add_entities, factory)
        self._sync_platform(key)

    def register_climate(self, add_entities: Callable, factory: ClimateEntityFactory) -> None:
        self._climate_add_entities = add_entities
        self._climate_factory = factory
        self._sync_climate()

    def _sync_all_platforms(self) -> None:
        for key in self._platforms:
            self._sync_platform(key)
        self._sync_climate()

    @callback
    def _sync_platform(self, key: str) -> None:
        topology = self.topology
        if topology is None:
            return
        add_entities, factory = self._platforms[key]
        existing = self._platform_entities.setdefault(key, {})
        wanted: dict[str, list[Entity]] = {}

        for point in topology.points.values():
            entities = factory(self, point)
            if entities:
                wanted[point.key] = entities

        for point_key, entities in wanted.items():
            if point_key not in existing:
                add_entities(entities)
                existing[point_key] = entities

        for point_key in list(existing):
            if point_key not in wanted:
                for entity in existing.pop(point_key):
                    self.hass.async_create_task(entity.async_remove())

    @callback
    def _sync_climate(self) -> None:
        if self._climate_factory is None or self._climate_added:
            return
        if self.topology is None or self._climate_add_entities is None:
            return
        entities = self._climate_factory(self)
        if entities:
            self._climate_add_entities(entities)
            self._climate_added = True

    def has_points(self, *keys: str) -> bool:
        if self.topology is None:
            return False
        return all(key in self.topology.points for key in keys)

    def value(self, key: str) -> float | None:
        return self.values.get(key)

    async def async_write_point(self, key: str, value: float) -> None:
        await self.call_service("nilan_write_point", {"key": key, "value": float(value)})

    async def async_press_point(self, key: str) -> None:
        point = self.topology.points.get(key) if self.topology else None
        value = float(point.max_value) if point and point.max_value is not None else 1.0
        await self.call_service("nilan_write_point", {"key": key, "value": value})

    async def async_commission(self) -> None:
        await self.call_service("nilan_commission", {})

    async def async_reset_alarm(self) -> None:
        await self.call_service("nilan_reset_alarm", {})

    async def call_service(self, name: str, data: dict[str, Any]) -> None:
        service = self.services.get(name)
        if service is None:
            _LOGGER.warning("ESPHome service %s is not available", name)
            return
        try:
            await self.client.execute_service(service, data)
        except ConnectionNotEstablishedAPIError:
            _LOGGER.warning("ESPHome connection lost during service call; reconnecting")
            await self._async_connect_and_discover()
            service = self.services.get(name)
            if service is not None:
                await self.client.execute_service(service, data)
