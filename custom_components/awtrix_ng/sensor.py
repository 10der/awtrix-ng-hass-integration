"""Platform for sensor integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import DOMAIN
from .coordinator import AwtrixCoordinator
from .entity import AwtrixEntity

ENTITY_ID_FORMAT = DOMAIN + ".{}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    coordinator: AwtrixCoordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            DeviceTemperatureSensor(hass=hass, coordinator=coordinator),
            DeviceHumiditySensor(hass=hass, coordinator=coordinator),
            BatteryChargeSensor(hass=hass, coordinator=coordinator),
            LuxSensor(hass=hass, coordinator=coordinator),
            # CommmonSensor(hass=hass, coordinator=coordinator,
            #                 key="app", name="Current app"),
            CommmonSensor(hass=hass, coordinator=coordinator,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            key="version", prefix="v", name="Version"),
            CommmonSensor(hass=hass, coordinator=coordinator, key="wifi_signal",
                            data_key="wifiRssi",
                            state_class=SensorStateClass.MEASUREMENT,
                            name="Wifi Signal",
                            entity_category=EntityCategory.DIAGNOSTIC,
                            icon="mdi:wifi"),
            CommmonSensor(hass=hass, coordinator=coordinator, key="ip_address",
                            data_key="ipAddress",
                            name="IP Address",
                            #state_class=SensorStateClass.MEASUREMENT,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            icon="mdi:wan"),
            CommmonSensor(hass=hass, coordinator=coordinator, key="uptime", name="Uptime",
                            data_key="uptimeSeconds",
                            device_class=SensorDeviceClass.DURATION,
                            state_class=SensorStateClass.MEASUREMENT,
                            measurement=UnitOfTime.SECONDS,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            icon="mdi:clock-outline"),
            CommmonSensor(hass=hass, coordinator=coordinator, key="ram", name="Free ram",
                            data_key="freeHeapBytes",
                            measurement="B",
                            entity_category=EntityCategory.DIAGNOSTIC,
                            state_class=SensorStateClass.MEASUREMENT,
                            icon="mdi:memory"),
            LastBootSensor(hass=hass, coordinator=coordinator),
        ]
    )

PARALLEL_UPDATES = 1

class CommmonSensor(AwtrixEntity, SensorEntity):
    """Representation of a common Sensor."""

    def __init__(self,
                 hass: HomeAssistant,
                 coordinator,
                 key,
                 name=None,
                 device_class=None,
                 state_class=None,
                 icon=None,
                 measurement=None,
                 entity_category=None,
                 value_fn=None,
                 prefix="",
                 suffix="",
                 data_key=None) -> None:
        """Initialize the entity."""
        self._attr_name = name or key
        self.hass = hass
        self.key = key
        self.data_key = data_key or key
        self.prefix = prefix
        self.suffix = suffix
        self.value_fn = value_fn

        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = measurement
        self._attr_entity_category = entity_category

        super().__init__(coordinator, key)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""

        value = self.coordinator.data.get(self.data_key)
        if value is not None:
            if self.value_fn is not None:
                value = self.value_fn(value)
            if self.prefix or self.suffix:
                self._attr_native_value = self.prefix + str(value) + self.suffix
            else:
                self._attr_native_value = value

        self.async_write_ha_state()


class DeviceTemperatureSensor(AwtrixEntity, SensorEntity):
    """Representation of a Sensor."""

    _attr_name = "Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        super().__init__(coordinator, "temperature")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""

        self._attr_native_value = self.coordinator.data.get("temperature", 0)
        self.async_write_ha_state()

class DeviceHumiditySensor(AwtrixEntity, SensorEntity):
    """Representation of a Sensor."""

    _attr_name = "Humidity"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        super().__init__(coordinator, "humidity")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""

        self._attr_native_value = self.coordinator.data.get("humidity", 0)
        self.async_write_ha_state()

class LuxSensor(AwtrixEntity, SensorEntity):
    """Representation of an Awtrix ambient light level sensor."""

    _attr_name = "Illuminance"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        super().__init__(coordinator, "lux")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""

        self._attr_native_value = self.coordinator.data.get("lightLevel", 0)
        self.async_write_ha_state()


class LastBootSensor(AwtrixEntity, SensorEntity):
    """Representation of an Awtrix last boot time sensor.

    Only updates (and fires a state change) when the computed boot time
    actually jumps, i.e. the device rebooted - unlike Uptime it stays
    constant between reboots, so it can be used as a reboot trigger.
    """

    _attr_name = "Last boot"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:restart"

    _REBOOT_THRESHOLD_SECONDS = 30

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        super().__init__(coordinator, "last_boot")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor only when the device actually rebooted."""

        uptime_seconds = self.coordinator.data.get("uptimeSeconds")
        if uptime_seconds is None:
            return

        boot_time = utcnow() - timedelta(seconds=uptime_seconds)
        previous = self._attr_native_value
        if previous is not None and abs((boot_time - previous).total_seconds()) <= self._REBOOT_THRESHOLD_SECONDS:
            return

        self._attr_native_value = boot_time
        self.async_write_ha_state()


class BatteryChargeSensor(AwtrixEntity, SensorEntity):
    """Representation of an Awtrix charge sensor."""

    _attr_name = "Battery"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        super().__init__(coordinator, "battery")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""

        self._attr_native_value = self.coordinator.data.get("batteryPercent", 0)
        self.async_write_ha_state()
