"""Constants for the Nilan Ventilation integration."""

from __future__ import annotations

DOMAIN = "auto_nilan"
DEFAULT_PORT = 6053
ENTRY_NAME = "Nilan Ventilation"

CONF_PASSWORD = "password"
CONF_NOISE_PSK = "noise_psk"

TEXT_TOPOLOGY = "topology"
TEXT_VALUES = "values"
TEXT_STATUS = "status"

TEXT_SENSOR_SUFFIXES: dict[str, str] = {
    TEXT_TOPOLOGY: "_topology",
    TEXT_VALUES: "_values",
    TEXT_STATUS: "_status",
}

# User services exposed by the auto_nilan ESPHome component.
SERVICE_WRITE_POINT = "nilan_write_point"
SERVICE_COMMISSION = "nilan_commission"
SERVICE_RESET_ALARM = "nilan_reset_alarm"

MANUFACTURER = "Nilan"

KIND_SENSOR = "sensor"
KIND_BINARY = "binary"
KIND_NUMBER = "number"
KIND_SELECT = "select"
KIND_SWITCH = "switch"
KIND_BUTTON = "button"
