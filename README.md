# Home Assistant AWTRIX NG Integration

[![Buy me a coffee](https://cdn.buymeacoffee.com/buttons/default-orange.png)](https://www.buymeacoffee.com/10der)

A Home Assistant integration for **AWTRIX NG**.

Supports:

- 🔔 Notifications
- 📱 Custom Apps
- ⚙️ Device Settings
- 🔊 Sounds & RTTTL
- 🎨 Draw API
- 💡 Indicators
- 🌙 Brightness & Power controls

> [!IMPORTANT]
> This integration supports **AWTRIX NG**.
>
> If you are upgrading from AWTRIX 3, please read the official migration guide:
>
> https://ang.blueforcer.de/guides/migrating-from-awtrix3/

---

# Installation

## Via HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=10der&repository=awtrix3-ng-hass-integration&category=Integration)

1. Search for **AWTRIX NG** in HACS.
2. Download the integration.
3. Restart Home Assistant.
4. Add the integration from **Settings → Devices & Services**.

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=awtrix3)

## Manual installation

Copy `custom_components/awtrix3/` into your Home Assistant `custom_components` directory, restart Home Assistant and add the integration through the UI.

---

# Notifications

```yaml
service: notify.awtrix_bedroom
data:
  message: Garage door has been open for 10 minutes.
```

With additional options:

```yaml
service: notify.awtrix_bedroom
data:
  message: Garage door has been open for 10 minutes.
  data:
    icon: "33655"
    sound: beep
```

---

# Persistent Notifications

Hold a notification on screen:

```yaml
service: notify.awtrix_bedroom
data:
  message: Hello!
  data:
    hold: true
```

Dismiss it:

```yaml
service: notify.awtrix_bedroom
data:
  message: ""
```

---

# Push Custom App

```yaml
service: awtrix.awtrix_bedroom_push_app_data
data:
  name: test
  data:
    text: Hello, AWTRIX!
    rainbow: true
    icon: "87"
    duration: 5
    pushIcon: 2
    lifetime: 900
    repeat: 1
```

Remove the app:

```yaml
service: awtrix.awtrix_bedroom_push_app_data
data:
  name: test
```

---

# Switch to App

```yaml
service: awtrix.awtrix_bedroom_switch_app
data:
  name: Time
```

---

# Device Settings

| Setting | Description |
|---------|-------------|
| BRI | Brightness |
| ABRI | Automatic brightness |
| TIME_COL | Clock color |
| TMODE | Clock mode |
| WD | Weekday display |
| ATRANS | Auto transitions |

Example:

```yaml
service: awtrix.awtrix_bedroom_settings
data:
  WD: false
  TIME_COL: [255, 0, 0]
  TMODE: 0
  BRI: 1
  ABRI: false
  ATRANS: false
```

Restore defaults:

```yaml
service: awtrix.awtrix_bedroom_settings
data:
  WD: true
  TIME_COL: [255,255,255]
  TMODE: 1
  BRI: 1
  ABRI: true
  ATRANS: true
```

---

# Sounds

RTTTL:

```yaml
service: awtrix.awtrix_bedroom_rtttl
data:
  rtttl: "two_short:d=4,o=5,b=100:16e6,16e6"
```

Built-in sound:

```yaml
service: awtrix.awtrix_bedroom_sound
data:
  sound: beep
```

---

# Examples

Bathroom temperature every 5 minutes:

```yaml
alias: Bathroom current temperature
trigger:
  - platform: time_pattern
    minutes: "/5"

action:
  - service: awtrix.awtrix_bedroom_push_app_data
    data:
      name: home_temperature
      data:
        text: "{{ states('sensor.bathroom_current_temperature') }}°"
        icon: "2056"
        duration: 5
        pushIcon: 2
        lifetime: 900
        repeat: 1
```

---

# Additional AWTRIX NG Features

The firmware also supports additional capabilities such as:

- Indicators
- Draw API
- Power control
- Brightness control
- Effects

Support for these services may depend on the integration version.
