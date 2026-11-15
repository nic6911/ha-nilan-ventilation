"""Live integration test against the auto_nilan firmware on the LAN.

Requires the Nilan controller to be reachable at NILAN_HOST (default
192.168.1.199) and no API encryption key.
"""

import asyncio
import ipaddress
import os

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from custom_components.auto_nilan.const import (
    CONF_NOISE_PSK,
    CONF_PASSWORD,
    DOMAIN,
    ENTRY_NAME,
)

NILAN_HOST = os.environ.get("NILAN_HOST", "192.168.1.199")
NILAN_MAC = os.environ.get("NILAN_MAC", "64:E8:33:00:DF:00")

pytestmark = pytest.mark.skipif(
    not os.environ.get("NILAN_LIVE_TEST"),
    reason="set NILAN_LIVE_TEST=1 to run against real hardware",
)


@pytest.mark.timeout(180)
async def test_live_config_flow_and_entities(hass) -> None:
    # The integration only needs aioesphomeapi (installed via the "esphome"
    # requirement in the manifest). The test environment lacks optional
    # components that the full ESPHome integration depends on, so mark it as
    # loaded before setting up the entry.
    hass.config.components.add("esphome")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: NILAN_HOST,
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_NOISE_PSK: "",
        },
    )
    assert result["type"] == "create_entry", result
    entry = result["result"]
    assert entry.title == ENTRY_NAME
    await hass.async_block_till_done()

    for _ in range(60):
        if entry.state is ConfigEntryState.LOADED:
            break
        await asyncio.sleep(0.5)
    assert entry.state is ConfigEntryState.LOADED

    for _ in range(60):
        if hass.states.async_entity_ids("climate"):
            break
        await asyncio.sleep(0.5)
    await hass.async_block_till_done()

    counts = {
        domain: len(hass.states.async_entity_ids(domain))
        for domain in ("sensor", "binary_sensor", "number", "select", "switch", "button", "climate")
    }
    print("entity counts:", counts)
    assert counts["sensor"] >= 30
    assert counts["number"] >= 30
    assert counts["select"] >= 10
    assert counts["switch"] >= 2
    assert counts["button"] >= 3
    assert counts["climate"] == 1

    online = [
        state
        for state in hass.states.async_all("binary_sensor")
        if "online" in (state.entity_id + state.name)
    ]
    print("online sensors:", [(s.entity_id, s.state) for s in online])
    assert online and any(s.state == "on" for s in online)

    climate_id = hass.states.async_entity_ids("climate")[0]
    climate = hass.states.get(climate_id)
    print(
        "climate:",
        climate.state,
        {
            key: climate.attributes.get(key)
            for key in (
                "current_temperature",
                "temperature",
                "fan_mode",
                "fan_modes",
                "hvac_modes",
                "min_temp",
                "max_temp",
                "target_temp_step",
            )
        },
    )
    print(
        "sample sensors:",
        [
            (s.entity_id, s.state, s.attributes.get("unit_of_measurement"))
            for s in hass.states.async_all("sensor")
            if s.entity_id.endswith(("_outdoor_temperature", "_room_temperature", "_humidity"))
        ],
    )

    numbers = hass.states.async_all("number")
    target = next((s for s in numbers if s.state not in ("unknown", "unavailable")), None)
    assert target is not None
    value = float(target.state)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": target.entity_id, "value": value},
        blocking=True,
    )
    await asyncio.sleep(12)
    await hass.async_block_till_done()
    after = hass.states.get(target.entity_id)
    assert after is not None and after.state == target.state

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.timeout(180)
async def test_live_zeroconf_discovery(hass) -> None:
    hass.config.components.add("esphome")
    hass.config.components.add("zeroconf")

    info = ZeroconfServiceInfo(
        ip_address=ipaddress.ip_address(NILAN_HOST),
        ip_addresses=[ipaddress.ip_address(NILAN_HOST)],
        port=6053,
        hostname="nilan-auto.local.",
        type="_esphomelib._tcp.local.",
        name="nilan-auto._esphomelib._tcp.local.",
        properties={
            "mac": NILAN_MAC,
            "friendly_name": "Nilan Auto",
            "version": "2026.10.2",
            "platform": "ESP32",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=info
    )
    assert result["type"] == "form", result
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry", result
    entry = result["result"]
    assert entry.title == ENTRY_NAME
    assert entry.data[CONF_HOST] == NILAN_HOST
    assert entry.unique_id == NILAN_MAC.replace(":", "").replace("-", "").upper()

    await hass.async_block_till_done()
    for _ in range(60):
        if entry.state is ConfigEntryState.LOADED:
            break
        await asyncio.sleep(0.5)
    assert entry.state is ConfigEntryState.LOADED

    for _ in range(60):
        if hass.states.async_entity_ids("climate"):
            await hass.async_block_till_done()
            break
        await asyncio.sleep(0.5)

    online = [
        state
        for state in hass.states.async_all("binary_sensor")
        if state.entity_id.endswith("_online")
    ]
    print("zeroconf online sensors:", [(s.entity_id, s.state) for s in online])
    assert online and all(s.state == "on" for s in online)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

