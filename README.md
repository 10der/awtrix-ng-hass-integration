# Home Assistant AWTRIX NG Integration

[![Buy me a coffee](https://cdn.buymeacoffee.com/buttons/default-orange.png)](https://www.buymeacoffee.com/10der)

A Home Assistant custom integration for **AWTRIX NG**.

## Features

Supports:

- 🔔 Notifications
- 📱 Pushed Apps
- ⚙️ Device Settings
- 🔄 App Switching
- 🔊 Built-in Sounds
- 🎵 RTTTL Melodies
- 📡 Multi-device Service Calls
- 🏠 Home Assistant Device Entities

> [!IMPORTANT]
> This integration is for **AWTRIX NG**.
>
> When migrating automations from AWTRIX 3, both the Home Assistant service convention and the AWTRIX payload keys must be updated.
>
> See the official migration guide: https://ang.blueforcer.de/guides/migrating-from-awtrix3/

## Installation

### HACS

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=10der&repository=awtrix-ng-hass-integration&category=Integration)

1. Open HACS.
2. Search for **AWTRIX NG**.
3. Download the integration.
4. Restart Home Assistant.
5. Add the integration from **Settings → Devices & services**.

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=awtrix_ng)

### Manual installation

Copy the entire `custom_components/awtrix_ng/` directory into:

```text
<config>/custom_components/awtrix_ng/
```

Restart Home Assistant and add **AWTRIX NG** from **Settings → Devices & services**.

## Notifications

The integration exposes a single `notify.awtrix_ng` action. Use `data.target` with the device's name (as shown on its device page, or renamed by you in Home Assistant) to send to a specific AWTRIX NG device, or omit `target` to send to all configured devices.

```yaml
action: notify.awtrix_ng
data:
  target: awtrix_bedroom
  message: Garage door has been open for 10 minutes.
```

Notification with additional AWTRIX NG payload fields:

```yaml
action: notify.awtrix_ng
data:
  target: awtrix_bedroom
  message: Garage door has been open for 10 minutes.
  data:
    icon: "33655"
    sound: beep
```

### Persistent notification

```yaml
action: notify.awtrix_ng
data:
  target: awtrix_bedroom
  message: Hello!
  data:
    hold: true
```

Dismiss the active notification by sending an empty message:

```yaml
action: notify.awtrix_ng
data:
  target: awtrix_bedroom
  message: ""
```

## Pushed apps

AWTRIX NG uses camelCase payload keys. Durations and lifetimes are specified in milliseconds.

```yaml
action: awtrix_ng.push_app_data
data:
  device_id:
    - YOUR_DEVICE_ID
  name: test
  data:
    text: Hello, AWTRIX NG!
    icon: "87"
    palette: Rainbow
    textColor: palette
    durationMs: 5000
    iconMode: push
    lifetimeMs: 900000
    repeat: 1
```

`device_id` accepts one or multiple AWTRIX NG device IDs.

### Remove a pushed app

For compatibility, this integration treats an empty app body as a request to remove the pushed app:

```yaml
action: awtrix_ng.push_app_data
data:
  device_id:
    - YOUR_DEVICE_ID
  name: test
  data: {}
```

The `data` field may also be omitted because it defaults to an empty object:

```yaml
action: awtrix_ng.push_app_data
data:
  device_id:
    - YOUR_DEVICE_ID
  name: test
```

## Switch to an app

```yaml
action: awtrix_ng.switch_app
data:
  device_id:
    - YOUR_DEVICE_ID
  name: Time
```

## Device settings

The `awtrix_ng.settings` action accepts AWTRIX NG setting names directly. Settings use camelCase.

Common settings include:

| Setting | Description |
|---|---|
| `brightness` | Panel brightness from 0 to 255 |
| `autoBrightness` | Use the light sensor for automatic brightness |
| `autoTransition` | Automatically rotate through apps |
| `appDurationMs` | Default app duration in milliseconds |
| `transitionEffect` | App transition effect |
| `transitionDurationMs` | Transition duration in milliseconds |
| `textColor` | Default text color |
| `timeMode` | Clock layout |
| `timeColor` | Clock text color |
| `volume` | Sound volume |

Example:

```yaml
action: awtrix_ng.settings
data:
  device_id:
    - YOUR_DEVICE_ID
  autoBrightness: false
  brightness: 120
  autoTransition: true
  appDurationMs: 7000
  transitionEffect: Fade
  transitionDurationMs: 1000
  timeMode: 1
  timeColor: "#FFFFFF"
```

Only the supplied settings are changed.

### Read settings

This action supports an optional response:

```yaml
action: awtrix_ng.get_settings
data:
  device_id:
    - YOUR_DEVICE_ID
response_variable: awtrix_settings
```

### Read device information

```yaml
action: awtrix_ng.get_device
data:
  device_id:
    - YOUR_DEVICE_ID
response_variable: awtrix_device
```

## Sounds

### Built-in sound

```yaml
action: awtrix_ng.sound
data:
  device_id:
    - YOUR_DEVICE_ID
  sound: beep
```

### RTTTL melody

```yaml
action: awtrix_ng.rtttl
data:
  device_id:
    - YOUR_DEVICE_ID
  rtttl: "two_short:d=4,o=5,b=100:16e6,16e6"
```

## Automation example

Show the bathroom temperature every five minutes:

```yaml
alias: Bathroom current temperature
description: Show the current bathroom temperature on AWTRIX NG
triggers:
  - trigger: time_pattern
    minutes: "/5"

conditions: []

actions:
  - action: awtrix_ng.push_app_data
    data:
      device_id:
        - YOUR_DEVICE_ID
      name: home_temperature
      data:
        text: "{{ states('sensor.bathroom_current_temperature') }}°"
        icon: "2056"
        durationMs: 5000
        iconMode: push
        lifetimeMs: 900000
        repeat: 1

mode: single
```

## Migrating AWTRIX 3 payloads

Some common payload conversions:

| AWTRIX 3 | AWTRIX NG |
|---|---|
| `color` | `textColor` |
| `rainbow: true` | `palette: Rainbow` and `textColor: palette` |
| `duration: 5` | `durationMs: 5000` |
| `lifetime: 900` | `lifetimeMs: 900000` |
| `pushIcon: 0` | `iconMode: fixed` |
| `pushIcon: 1` | `iconMode: pushOnce` |
| `pushIcon: 2` | `iconMode: push` |
| `scrollSpeed: 50` | `scroll: { speed: 50 }` |
| `noScroll: true` | `scroll: { mode: static }` |
| `progressC` | `progressColor` |
| `progressBC` | `progressTrackColor` |
| `bar` | `barChart` |
| `line` | `lineChart` |
| `rtttl` in notification data | `soundRtttl` |

AWTRIX NG validates payloads strictly. Unknown or obsolete keys cause the whole request to be rejected instead of being silently ignored.

## Notes

- Pushed app names must contain only letters, numbers, `_` or `-` and must be between 1 and 32 characters long.
- AWTRIX NG app payloads use camelCase.
- Time values ending in `Ms` are expressed in milliseconds.
- The integration can target multiple configured devices in one action by placing multiple values in `device_id`.
