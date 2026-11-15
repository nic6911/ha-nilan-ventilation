# Nilan Ventilation

Home Assistant integration for Nilan ventilation units running the `auto_nilan`
ESPHome firmware:

- **Nilan CTS602** (full controller)
- **Nilan CTS602 Light**
- **Nilan CTS400**

The firmware detects the controller, its model and its capabilities, then
publishes a topology JSON. This integration turns that topology into Home
Assistant entities automatically - no per-unit YAML, no register list, no MQTT.

[![Open in Marketplace](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=nic6911&repository=ha-nilan-ventilation&category=integration)

> **Status:** 0.2.0. The matching ESPHome component is on the
> [`feature/nilan_auto_discovery`](https://github.com/nic6911/esphome_components/tree/feature/nilan_auto_discovery)
> branch until it is merged upstream. CTS602 is validated on real hardware;
> CTS602 Light and CTS400 are implemented from the Nilan Modbus documentation and
> need field reports.

---

## Start here

You need two things: the ESP32 firmware and this integration.

### 1. Flash the ESP32

Use the ready-made YAML for the ESP32 Modbus Module:

- **Rev1 (direction pin GPIO10):**
  [nilan_ventilation_auto.yaml](https://github.com/nic6911/ESP32_Modbus_Module/blob/main/esphome_example_code/rev1/nilan_ventilation_auto.yaml)
- **Rev2 (direction pin GPIO3):**
  [nilan_ventilation_auto.yaml](https://github.com/nic6911/ESP32_Modbus_Module/blob/main/esphome_example_code/rev2/nilan_ventilation_auto.yaml)

Firmware documentation, options and manual setup:

**[auto_nilan component README](https://github.com/nic6911/esphome_components/blob/feature/nilan_auto_discovery/components/auto_nilan/README.md)**

The short version:

1. Wire the module to the Nilan Modbus terminals (19200 8E1, address 30).
2. Open ESPHome, create a device, paste the YAML.
3. Set Wi-Fi credentials and install it.
4. Wait until the ESPHome device is online.

The firmware commissions itself and keeps retrying until it finds the controller.

### 2. Install this integration

1. Go to **Settings -> Marketplace** in Home Assistant.
2. Select **Add from link**.
3. Enter this repository:

   ```text
   https://github.com/nic6911/ha-nilan-ventilation
   ```

4. If Marketplace asks for a type, choose **Integration**.
5. Open **Nilan Ventilation** and select **Install**.
6. If Home Assistant asks to restart, restart it.

### 3. Add the unit in Home Assistant

Home Assistant normally discovers the module automatically after it is online.

1. Wait for a discovered **Nilan Ventilation** card and select **Configure**.
2. Confirm the device. You do not need to enter an IP address.
3. If discovery does not appear, use **Add integration** -> **Nilan Ventilation**
   and enter the ESP32 host name or IP address as a fallback. Leave the API key
   empty unless you enabled ESPHome API encryption.

That is it. No MQTT broker is needed.

---

## What you get

Entities are created from the firmware topology, so the list matches your unit:

| Platform | Typical content |
|---|---|
| `sensor` | Temperatures, humidity, CO2, pressure, capacity, fan speed, status values |
| `binary_sensor` | Online, alarms, damper/valve states, summer mode, user functions |
| `number` | Temperature setpoints, fan/timer values, user function settings |
| `select` | Operating mode, fan step, week program, sensor/heat source selection |
| `switch` | On/off functions |
| `button` | User function buttons, **Commission**, **Alarm reset** |
| `climate` | CTS602: operation mode, fan step and current temperature |

A CTS602 typically exposes around 120 entities. CTS400 exposes fewer points.

### Climate entity

For CTS602 the integration adds one climate entity:

- Modes: **Off**, **Heat**, **Auto**, plus **Cool** when the unit reports a
  cooling capability.
- Fan steps from the ventilation `vent_set` options.
- Current temperature from the controller's controlled temperature
  (`temp_control`), falling back to the actual room temperature.

### Diagnostics

The integration adds an **Online** binary sensor and diagnostic sensors for poll
duration and Modbus counters. Those counter sensors are disabled by default; the
firmware's **Nilan Status** text sensor has the full status JSON.

## Automatic detection and topology

The firmware:

1. Detects CTS602 (input register 0 + holding register 1000) or CTS400 (input
   register 24 + holding register 37).
2. Probes capabilities such as RH, CO2, VOC, cooling, heating, hot water,
   bypass, preheat and pressure.
3. Probes optional registers and removes points the controller reports as illegal.
4. Publishes the topology, current values and status.

This integration reads those text sensors, subscribes to the ESPHome Native API
and keeps the entities updated. When the firmware topology changes, reload the
integration (or restart Home Assistant) so the entity list is rebuilt.

### Commissioning

Commissioning is automatic. You can force it with the **Commission** button on
the integration device, the firmware's `nilan_commission` service, or by
restarting the ESP32.

Writes are applied through the firmware: CTS602 uses Modbus function `0x10`,
CTS400 uses `0x06`.

## Supported controllers

| Controller | Detection | Status |
|---|---|---|
| CTS602 | Input register 0 + holding register 1000 | Validated on VPL 10 without cooling |
| CTS602 Light | Same register map as CTS602; optional points pruned | Implemented, needs field validation |
| CTS400 | Input register 24 + holding register 37 | Implemented, needs field validation |

## Troubleshooting

| Problem | Try |
|---|---|
| Integration is not discovered | Check that the ESP32 and Home Assistant are on the same network/VLAN and that mDNS works; add it manually with the IP address |
| Cannot connect | Check TCP port `6053`, the ESP32 IP address, and the ESPHome API password/encryption key |
| No entities appear | Confirm the firmware publishes `Nilan Topology` and `Nilan Values` text sensors and is commissioned |
| Values are `unknown` / `unavailable` | Check the firmware status sensor and ESPHome logs for `no Nilan controller detected` |
| Some entities are missing | The unit does not implement those registers; the firmware pruned them during commissioning |
| A write does not change the unit | Confirm the entity is writable; CTS400 write behavior is not hardware-validated yet |
| Old entities remain | Reload the integration or delete the stale entities manually |
| Duplicate Nilan devices | Remove the old ESPHome device entry or the old integration entry, then restart |

## Compatibility

- Home Assistant 2026.2 or newer (tested on 2026.11)
- ESPHome firmware `auto_nilan` from the
  `feature/nilan_auto_discovery` branch
- ESPHome Native API on local TCP port `6053` (no port forwarding)
- Topology JSON version `1`

## Manual installation

Copy `custom_components/auto_nilan` into your Home Assistant
`custom_components` directory, restart Home Assistant, and add the integration.

## Development

The repository includes a live-hardware test suite. It needs a reachable unit
and no API encryption key:

```powershell
$env:NILAN_LIVE_TEST = "1"
$env:NILAN_HOST = "192.168.1.199"
python -m pytest tests
```

Two tests run: the manual add flow and the zeroconf discovery flow. They verify
entry creation, entity counts, the climate entity, a number write round-trip and
unloading.

Issue tracker:
<https://github.com/nic6911/ha-nilan-ventilation/issues>
