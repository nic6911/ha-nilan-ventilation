"""Config and options flow for the Nilan Ventilation integration."""

from __future__ import annotations

import asyncio
import logging

from aioesphomeapi import (
    APIConnectionError,
    APIClient,
    InvalidAuthAPIError,
    InvalidEncryptionKeyAPIError,
    RequiresEncryptionAPIError,
    TextSensorInfo,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_NOISE_PSK,
    CONF_PASSWORD,
    DEFAULT_PORT,
    DOMAIN,
    ENTRY_NAME,
    TEXT_SENSOR_SUFFIXES,
)
from .coordinator import NilanCoordinator

_LOGGER = logging.getLogger(__name__)


def _normalize_mac(mac: str) -> str:
    return mac.replace(":", "").replace("-", "").upper()


def _property(properties: dict, key: str) -> str:
    value = properties.get(key)
    if isinstance(value, bytes):
        value = value.decode(errors="replace")
    return (value or "").strip()


def _schema(defaults: dict | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Optional(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Optional(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): str,
            vol.Optional(CONF_NOISE_PSK, default=defaults.get(CONF_NOISE_PSK, "")): str,
        }
    )


class AutoNilanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a Nilan ventilation unit."""

    VERSION = 2

    def __init__(self) -> None:
        self._host: str = ""
        self._port: int = DEFAULT_PORT
        self._name: str = ""
        self._noise_required = False

    async def _async_probe(
        self, host: str, port: int, password: str, noise_psk: str
    ) -> tuple[str, str, set[str]]:
        client = APIClient(
            host,
            port,
            password or None,
            noise_psk=noise_psk or None,
            client_info="ha-nilan-ventilation",
        )
        try:
            async with asyncio.timeout(20):
                await client.connect(login=True)
                device_info = await client.device_info()
                entities, _services = await client.list_entities_services()
        finally:
            await client.disconnect()

        if device_info is None:
            raise RuntimeError("ESPHome device information is unavailable")

        found: set[str] = set()
        for info in entities:
            if isinstance(info, TextSensorInfo):
                kind = NilanCoordinator.classify_text_sensor(info)
                if kind is not None:
                    found.add(kind)

        mac = _normalize_mac(device_info.mac_address) or f"host_{host}"
        title = device_info.friendly_name or device_info.name or host
        return mac, title, found

    @staticmethod
    def _is_nilan(found: set[str]) -> bool:
        return not (set(TEXT_SENSOR_SUFFIXES) - found)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle automatic discovery of the ESPHome device."""
        properties = discovery_info.properties
        mac = _property(properties, "mac")
        if not mac:
            return self.async_abort(reason="mdns_missing_mac")

        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT
        await self.async_set_unique_id(_normalize_mac(mac))
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: host, CONF_PORT: port}
        )

        hostname = (discovery_info.hostname or host).removesuffix(".local.")
        self._host = host
        self._port = port
        self._name = _property(properties, "friendly_name") or hostname
        self._noise_required = bool(_property(properties, "api_encryption"))

        name_hint = f"{self._name} {hostname}".lower()
        if self._noise_required and "nilan" not in name_hint:
            return self.async_abort(reason="not_nilan")

        if not self._noise_required:
            try:
                mac, name, found = await self._async_probe(host, port, "", "")
            except RequiresEncryptionAPIError:
                self._noise_required = True
            except (APIConnectionError, TimeoutError, OSError):
                _LOGGER.debug("Unable to probe ESPHome device at %s", host)
                return self.async_abort(reason="cannot_connect")
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error while probing %s", host)
                return self.async_abort(reason="cannot_connect")
            else:
                if not self._is_nilan(found):
                    return self.async_abort(reason="not_nilan")
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: host, CONF_PORT: port}
                )
                self._name = name or self._name

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Confirm a discovered unit, asking for a key only when required."""
        errors: dict[str, str] = {}

        if user_input is not None:
            noise_psk = (user_input.get(CONF_NOISE_PSK) or "").strip()
            if self._noise_required:
                try:
                    mac, name, found = await self._async_probe(
                        self._host, self._port, "", noise_psk
                    )
                except InvalidEncryptionKeyAPIError:
                    errors["base"] = "invalid_encryption_key"
                except (APIConnectionError, TimeoutError, OSError):
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error while probing %s", self._host)
                    errors["base"] = "unknown"
                else:
                    if not self._is_nilan(found):
                        errors["base"] = "not_nilan"
                    else:
                        await self.async_set_unique_id(mac)
                        self._abort_if_unique_id_configured(
                            updates={CONF_HOST: self._host, CONF_PORT: self._port}
                        )
                        self._name = name or self._name
                        return self._async_create_entry(noise_psk)
            else:
                return self._async_create_entry("")

        data_schema = (
            vol.Schema({vol.Optional(CONF_NOISE_PSK, default=""): str})
            if self._noise_required
            else vol.Schema({})
        )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._name},
            data_schema=data_schema,
            errors=errors,
        )

    def _async_create_entry(self, noise_psk: str) -> FlowResult:
        return self.async_create_entry(
            title=ENTRY_NAME,
            data={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_PASSWORD: "",
                CONF_NOISE_PSK: noise_psk,
            },
        )

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            password = user_input.get(CONF_PASSWORD) or ""
            noise_psk = (user_input.get(CONF_NOISE_PSK) or "").strip()
            try:
                mac, _name, found = await self._async_probe(
                    host, port, password, noise_psk
                )
            except InvalidAuthAPIError:
                errors["base"] = "invalid_auth"
            except InvalidEncryptionKeyAPIError:
                errors["base"] = "invalid_encryption_key"
            except RequiresEncryptionAPIError:
                errors["base"] = "encryption_required"
            except (APIConnectionError, TimeoutError, OSError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error while probing Nilan device")
                errors["base"] = "unknown"
            else:
                if not self._is_nilan(found):
                    errors["base"] = "not_nilan"
                else:
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: host, CONF_PORT: port}
                    )
                    return self.async_create_entry(
                        title=ENTRY_NAME,
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_PASSWORD: password,
                            CONF_NOISE_PSK: noise_psk,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return AutoNilanOptionsFlow(config_entry)


class AutoNilanOptionsFlow(config_entries.OptionsFlow):
    """Update the connection settings of a configured unit."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> FlowResult:
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            data = {
                CONF_HOST: host,
                CONF_PORT: int(user_input[CONF_PORT]),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD) or "",
                CONF_NOISE_PSK: (user_input.get(CONF_NOISE_PSK) or "").strip(),
            }
            self.hass.config_entries.async_update_entry(self.entry, data=data)
            return self.async_create_entry(title="", data={})

        defaults = dict(self.entry.data)
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(defaults),
        )
