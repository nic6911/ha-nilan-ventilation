# Nilan Ventilation - Quick Start

Your ESP32 module is flashed and the Nilan unit is connected. You only need to
connect the module to Wi-Fi and add it to Home Assistant.

**You need**

- A 2.4 GHz Wi-Fi network
- Home Assistant 2026.2 or newer with **Marketplace**
- The Nilan unit powered on and Modbus enabled
- The RS-485 cable connected to the module (A/B, 19200 8E1, address 30)

> ESP32 does not support 5 GHz Wi-Fi. If your router uses separate names, use the
> 2.4 GHz one.

---

## 1. Power the module

Connect the module to the Nilan unit and power it on.

Wait **1-2 minutes**. The module tries to join Wi-Fi. If it cannot, it creates a
setup hotspot.

## 2. Connect to the setup hotspot

On your phone or laptop, connect to:

```text
Nilan Fallback Hotspot
```

Open `http://192.168.4.1` if the setup page does not open automatically. Enter
your Wi-Fi name and password and save. The module restarts and joins your Wi-Fi.

## 3. Install the integration

1. Go to **Settings -> Marketplace**.
2. Select **Add from link** and enter:

   ```text
   https://github.com/nic6911/ha-nilan-ventilation
   ```

3. Choose **Integration** if asked, install **Nilan Ventilation**, and restart
   Home Assistant if prompted.

## 4. Add the unit

Home Assistant normally finds the module automatically.

1. Select **Configure** on the discovered **Nilan Ventilation** card.
2. Confirm the device. No IP address is needed.

If no discovery card appears, use **Add integration** -> **Nilan Ventilation**
and enter the ESP32 host name or IP address. Leave the API key empty.

## 5. Check the entities

You should see sensors for temperatures, humidity and status, plus numbers,
selects and (on CTS602) a climate entity.

Open the climate entity and try changing the mode or fan step. The Nilan unit
should follow. Number entities for setpoints and timers can be changed the same
way.

The **Commission** button re-scans the controller. The **Alarm reset** button
clears alarms.

## If something does not work

| Problem | Try |
|---|---|
| The setup hotspot is not visible | Wait another minute, then power-cycle the module |
| The setup page does not open | Open `http://192.168.4.1` manually |
| No discovery card | Add the integration manually with the ESP32 IP address |
| No entities | Check the ESPHome log for `no Nilan controller detected`; verify A/B wiring and address 30 |
| Values are unavailable | Check that the Nilan unit is powered and Modbus is enabled |
| Writes do not work | Confirm the entity is writable; CTS400 write support needs field validation |

Need help? Open an issue:

```text
https://github.com/nic6911/ha-nilan-ventilation/issues
```
