"""Automatic discovery of entities from the AWTRIX NG ``/api/v1/device`` payload.

Every scalar field of the device payload (nested objects are flattened) becomes
an entity: numbers and text become sensors, booleans become binary sensors.
New fields that a later firmware adds show up on their own, without a code
change. Fields that already have a dedicated entity are skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfInformation,
    UnitOfTime,
)

# Top-level fields that are already exposed by a dedicated entity (or are used
# as identity) and must therefore not be created a second time.
EXCLUDED_KEYS: frozenset[str] = frozenset(
    {
        "uid",
        "version",
        "ipAddress",
        "wifiRssi",
        "uptimeSeconds",
        "freeHeapBytes",
        "batteryPercent",
        "lightLevel",
        "temperature",
        "humidity",
        "brightness",  # light.matrix
        "matrixPower",  # light.matrix
        "indicators",  # light.indicator1..3
    }
)

# Words that should keep a fixed spelling in generated names.
_WORD_OVERRIDES = {
    "mqtt": "MQTT",
    "wifi": "Wifi",
    "fps": "FPS",
    "usb": "USB",
    "mac": "MAC",
    "soc": "SoC",
    "ip": "IP",
}


@dataclass(frozen=True)
class DeviceField:
    """One scalar leaf of the device payload."""

    key: str  # flattened snake_case key, e.g. "mqtt_last_error"
    path: tuple[str, ...]  # path into the payload, e.g. ("mqtt", "lastError")
    name: str  # human readable name
    value: Any  # value at discovery time (decides sensor vs. binary sensor)

    @property
    def is_binary(self) -> bool:
        """Booleans become binary sensors."""
        return isinstance(self.value, bool)


@dataclass(frozen=True)
class SensorMeta:
    """Presentation details for a numeric/text sensor."""

    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    unit: str | None = None
    suggested_unit: str | None = None
    precision: int | None = None
    icon: str | None = None
    category: EntityCategory | None = EntityCategory.DIAGNOSTIC


@dataclass(frozen=True)
class BinaryMeta:
    """Presentation details for a binary sensor."""

    device_class: BinarySensorDeviceClass | None = None
    icon: str | None = None
    category: EntityCategory | None = EntityCategory.DIAGNOSTIC


# Explicit metadata for fields we know. Keys are flattened snake_case keys.
KNOWN_SENSORS: dict[str, SensorMeta] = {
    "current_app": SensorMeta(icon="mdi:application", category=None),
    "battery_voltage": SensorMeta(
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        unit=UnitOfElectricPotential.VOLT,
        precision=2,
    ),
    "fps": SensorMeta(
        state_class=SensorStateClass.MEASUREMENT, unit="fps", icon="mdi:speedometer"
    ),
    "message_count": SensorMeta(
        state_class=SensorStateClass.TOTAL_INCREASING, icon="mdi:message-text"
    ),
    "wifi_connects": SensorMeta(
        state_class=SensorStateClass.TOTAL_INCREASING, icon="mdi:wifi-refresh"
    ),
    "mqtt_connects": SensorMeta(
        state_class=SensorStateClass.TOTAL_INCREASING, icon="mdi:lan-connect"
    ),
    "wifi_state": SensorMeta(icon="mdi:wifi"),
    "mqtt_state": SensorMeta(icon="mdi:lan-connect"),
    "reset_reason": SensorMeta(icon="mdi:restart-alert"),
    "board_type": SensorMeta(icon="mdi:chip"),
    "soc": SensorMeta(icon="mdi:chip"),
    "hostname": SensorMeta(icon="mdi:dns"),
    "mac_address": SensorMeta(icon="mdi:network"),
    "update_state": SensorMeta(icon="mdi:update"),
    "update_release": SensorMeta(icon="mdi:tag"),
    "update_error": SensorMeta(icon="mdi:alert-circle-outline"),
    "mirror_state": SensorMeta(icon="mdi:monitor-eye"),
    "mirror_viewers": SensorMeta(
        state_class=SensorStateClass.MEASUREMENT, icon="mdi:eye"
    ),
}

KNOWN_BINARY: dict[str, BinaryMeta] = {
    "low_battery": BinaryMeta(device_class=BinarySensorDeviceClass.BATTERY),
    "usb_power": BinaryMeta(device_class=BinarySensorDeviceClass.POWER),
    "scripting_running": BinaryMeta(device_class=BinarySensorDeviceClass.RUNNING),
}


def snake_case(text: str) -> str:
    """Convert camelCase (and dotted/underscored) names to snake_case."""
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text)
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()


def humanize(parts: tuple[str, ...]) -> str:
    """Build a readable name like "MQTT last error" from a payload path."""
    words: list[str] = []
    for part in parts:
        words.extend(w for w in snake_case(part).split("_") if w)
    rendered = [_WORD_OVERRIDES.get(word, word) for word in words]
    if rendered and rendered[0] == rendered[0].lower():
        rendered[0] = rendered[0].capitalize()
    return " ".join(rendered)


def _flatten(
    data: dict[str, Any], prefix: tuple[str, ...] = ()
) -> list[tuple[tuple[str, ...], Any]]:
    """Return every scalar leaf of ``data`` together with its path.

    Lists are skipped: they hold structured items (e.g. indicators) that
    cannot be represented as a single state.
    """
    leaves: list[tuple[tuple[str, ...], Any]] = []
    for key, value in data.items():
        path = (*prefix, key)
        if isinstance(value, dict):
            leaves.extend(_flatten(value, path))
        elif isinstance(value, (bool, int, float, str)) or value is None:
            leaves.append((path, value))
    return leaves


def discover_fields(device_data: dict[str, Any]) -> list[DeviceField]:
    """Discover all fields of the device payload that should get an entity."""
    fields: list[DeviceField] = []
    for path, value in _flatten(device_data):
        if len(path) == 1 and path[0] in EXCLUDED_KEYS:
            continue
        fields.append(
            DeviceField(
                key=snake_case("_".join(path)),
                path=path,
                name=humanize(path),
                value=value,
            )
        )
    return fields


def resolve_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    """Read a value from nested payload data, ``None`` if it is missing."""
    current: Any = data
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def sensor_meta_for(field: DeviceField) -> SensorMeta:
    """Metadata for a sensor field: explicit if known, else guessed from the name.

    Guessing only applies to numeric values, so a device class/unit can never
    end up on a text value.
    """
    if field.key in KNOWN_SENSORS:
        return KNOWN_SENSORS[field.key]

    numeric = isinstance(field.value, (int, float)) and not isinstance(
        field.value, bool
    )
    if not numeric:
        return SensorMeta()

    name = field.path[-1]
    if name.endswith("Bytes"):
        return SensorMeta(
            device_class=SensorDeviceClass.DATA_SIZE,
            state_class=SensorStateClass.MEASUREMENT,
            unit=UnitOfInformation.BYTES,
            suggested_unit=UnitOfInformation.MEGABYTES,
            precision=2,
        )
    if name.endswith("Ms"):
        return SensorMeta(
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            unit=UnitOfTime.MILLISECONDS,
        )
    if name.endswith("Seconds"):
        return SensorMeta(
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            unit=UnitOfTime.SECONDS,
        )
    if name.endswith("Voltage"):
        return SensorMeta(
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            unit=UnitOfElectricPotential.VOLT,
        )
    if name.endswith("Percent"):
        return SensorMeta(
            state_class=SensorStateClass.MEASUREMENT, unit=PERCENTAGE
        )
    return SensorMeta(state_class=SensorStateClass.MEASUREMENT)


def binary_meta_for(field: DeviceField) -> BinaryMeta:
    """Metadata for a binary sensor field."""
    return KNOWN_BINARY.get(field.key, BinaryMeta())
