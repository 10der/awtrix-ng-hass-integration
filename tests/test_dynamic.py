"""Tests for automatic sensor discovery from the /api/v1/device payload."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.awtrix_ng.const import DOMAIN
from custom_components.awtrix_ng.dynamic import (
    DeviceField,
    discover_fields,
    humanize,
    resolve_path,
    sensor_meta_for,
    snake_case,
)

# Real response of an Ulanzi TC001/TC002 running AWTRIX NG 1.2.2.
DEVICE = {
    "version": "1.2.2",
    "uid": "ccc4b277a14e",
    "boardType": "tc002",
    "soc": "armv7l",
    "updateImage": "awtrix-ng-tc002.awup",
    "ipAddress": "192.168.2.147",
    "macAddress": "CC:C4:B2:77:A1:4E",
    "hostname": "AwtrixUlanzi2",
    "wifiRssi": -48,
    "uptimeSeconds": 10956,
    "freeHeapBytes": 12709888,
    "minFreeHeapBytes": 12644352,
    "scriptingRunning": True,
    "scriptHeapPool": "system",
    "scriptHeapBudgetBytes": 4194304,
    "resetReason": "software",
    "fps": 42,
    "brightness": 51,
    "batteryPercent": 76,
    "batteryVoltage": 4.13,
    "lowBattery": False,
    "matrixPower": True,
    "currentApp": "Treffen",
    "indicators": [
        {"on": False, "color": "#000000", "blinkMs": 0, "fadeMs": 0},
        {"on": False, "color": "#000000", "blinkMs": 0, "fadeMs": 0},
        {"on": False, "color": "#000000", "blinkMs": 0, "fadeMs": 0},
    ],
    "messageCount": 822,
    "wifi": {
        "enabled": True,
        "state": "connected",
        "host": "ssid",
        "endpoint": "192.168.2.147",
        "attempts": 0,
        "retryInMs": 0,
        "connects": 1,
        "error": None,
        "lastError": None,
    },
    "mqtt": {
        "enabled": True,
        "state": "connected",
        "host": "192.168.2.67",
        "endpoint": "192.168.2.67:1883",
        "attempts": 0,
        "retryInMs": 0,
        "connects": 1,
        "error": None,
        "lastError": "refused",
    },
    "mirror": {"sharing": False, "viewers": 0, "source": "", "state": "off"},
    "usbPower": True,
    "update": {
        "state": "confirmed",
        "release": "1.2.2-ga02f3ab66cd8-c701ad018299",
        "error": "",
    },
}
SETTINGS = {"autoBrightness": True}


def _by_key(data: dict) -> dict[str, DeviceField]:
    return {f.key: f for f in discover_fields(data)}


def test_naming_helpers() -> None:
    """camelCase paths become snake_case keys and readable names."""
    assert snake_case("minFreeHeapBytes") == "min_free_heap_bytes"
    assert humanize(("minFreeHeapBytes",)) == "Min free heap bytes"
    assert humanize(("mqtt", "lastError")) == "MQTT last error"
    assert humanize(("fps",)) == "FPS"


def test_resolve_path() -> None:
    """Nested values resolve, missing ones are None."""
    assert resolve_path(DEVICE, ("mqtt", "state")) == "connected"
    assert resolve_path(DEVICE, ("mqtt", "nope")) is None
    assert resolve_path(DEVICE, ("fps", "deeper")) is None


def test_discovery_covers_new_fields() -> None:
    """Fields without a dedicated entity are discovered, nested ones flattened."""
    fields = _by_key(DEVICE)

    for key in (
        "board_type",
        "soc",
        "update_image",
        "mac_address",
        "hostname",
        "min_free_heap_bytes",
        "scripting_running",
        "script_heap_pool",
        "script_heap_budget_bytes",
        "reset_reason",
        "fps",
        "battery_voltage",
        "low_battery",
        "current_app",
        "message_count",
        "usb_power",
        "wifi_enabled",
        "wifi_state",
        "wifi_connects",
        "wifi_last_error",
        "mqtt_state",
        "mqtt_last_error",
        "mirror_sharing",
        "mirror_viewers",
        "update_state",
        "update_release",
        "update_error",
    ):
        assert key in fields, key


def test_discovery_skips_existing_entities() -> None:
    """Fields that already have a sensor/light, plus lists, are not duplicated."""
    fields = _by_key(DEVICE)

    for key in (
        "uid",
        "version",
        "ip_address",
        "wifi_rssi",
        "uptime_seconds",
        "free_heap_bytes",
        "battery_percent",
        "brightness",
        "matrix_power",
        "indicators",
    ):
        assert key not in fields, key


def test_discovery_picks_up_unknown_future_field() -> None:
    """A field no code knows about still gets an entity."""
    data = deepcopy(DEVICE)
    data["someNewMetric"] = 7
    data["newFlag"] = True
    fields = _by_key(data)

    assert fields["some_new_metric"].is_binary is False
    assert fields["new_flag"].is_binary is True


def test_binary_vs_sensor_split() -> None:
    """Only real booleans become binary sensors."""
    fields = _by_key(DEVICE)

    assert fields["low_battery"].is_binary
    assert fields["usb_power"].is_binary
    assert not fields["fps"].is_binary
    assert not fields["wifi_last_error"].is_binary  # None -> sensor


def test_sensor_meta_known_and_guessed() -> None:
    """Known fields get explicit metadata, unknown numeric ones are guessed."""
    fields = _by_key(DEVICE)

    assert sensor_meta_for(fields["battery_voltage"]).unit == "V"
    assert sensor_meta_for(fields["min_free_heap_bytes"]).unit == "B"
    assert sensor_meta_for(fields["wifi_retry_in_ms"]).unit == "ms"
    # Text values never get a unit or device class.
    meta = sensor_meta_for(fields["update_release"])
    assert meta.unit is None and meta.device_class is None


async def test_entities_created_and_updated(hass: HomeAssistant) -> None:
    """Setting up the integration exposes the new fields and follows new ones."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ccc4b277a14e",
        data={CONF_HOST: "192.0.2.10", CONF_USERNAME: "", CONF_PASSWORD: ""},
    )
    entry.add_to_hass(hass)

    device = deepcopy(DEVICE)
    with (
        patch(
            "custom_components.awtrix_ng.awtrix_ng_api.AwtrixNgApi.async_get_device",
            AsyncMock(side_effect=lambda: deepcopy(device)),
        ),
        patch(
            "custom_components.awtrix_ng.awtrix_ng_api.AwtrixNgApi.async_get_settings",
            AsyncMock(return_value=SETTINGS),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)

        def state_of(domain: str, name: str):
            entity_id = next(
                e.entity_id
                for e in er.async_entries_for_config_entry(registry, entry.entry_id)
                if e.domain == domain and e.original_name == name
            )
            return hass.states.get(entity_id)

        assert state_of("sensor", "Battery voltage").state == "4.13"
        assert state_of("sensor", "Current app").state == "Treffen"
        assert state_of("sensor", "MQTT state").state == "connected"
        assert state_of("sensor", "Message count").state == "822"
        assert state_of("binary_sensor", "Low battery").state == "off"
        assert state_of("binary_sensor", "USB power").state == "on"
        # Empty string ("no error") is shown as unknown rather than a blank state.
        assert state_of("sensor", "Update error").state == "unknown"

        # A field that only a newer firmware reports appears after the next poll.
        device["brandNewSensor"] = 5
        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        assert state_of("sensor", "Brand new sensor").state == "5"

        assert await hass.config_entries.async_unload(entry.entry_id)
