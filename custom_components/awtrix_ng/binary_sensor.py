"""Awtrix platform binary sensors."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AwtrixCoordinator
from .dynamic import DeviceField, binary_meta_for, discover_fields, resolve_path
from .entity import AwtrixEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    coordinator: AwtrixCoordinator = entry.runtime_data.coordinator

    async_add_entities([
        AwtrixBinarySensor(
            hass=hass,
            coordinator=coordinator,
            key="button_left",
            name="Button left",
            icon="mdi:chevron-left-box-outline"),
        AwtrixBinarySensor(
            hass=hass,
            coordinator=coordinator,
            key="button_select",
            name="Button select",
            icon="mdi:circle-box-outline"),
        AwtrixBinarySensor(
            hass=hass,
            coordinator=coordinator,
            key="button_right",
            name="Button right",
            icon="mdi:chevron-right-box-outline")
    ])

    # Every true/false field of /api/v1/device gets a binary sensor automatically.
    # Re-checked on each poll so fields added by a newer firmware appear
    # without reloading the integration.
    known_keys: set[str] = set()

    @callback
    def _add_new_binary_sensors() -> None:
        new_entities: list[AwtrixDynamicBinarySensor] = []
        for field in discover_fields(coordinator.device_data):
            if not field.is_binary or field.key in known_keys:
                continue
            known_keys.add(field.key)
            new_entities.append(
                AwtrixDynamicBinarySensor(
                    hass=hass, coordinator=coordinator, field=field
                )
            )
        if new_entities:
            async_add_entities(new_entities)

    _add_new_binary_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_binary_sensors))

PARALLEL_UPDATES = 1


class AwtrixDynamicBinarySensor(AwtrixEntity, BinarySensorEntity):
    """Binary sensor created automatically for a boolean device field."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: AwtrixCoordinator,
        field: DeviceField,
    ) -> None:
        """Initialize the binary sensor."""
        meta = binary_meta_for(field)
        self.hass = hass
        self._path = field.path
        self._attr_name = field.name
        self._attr_device_class = meta.device_class
        self._attr_icon = meta.icon
        self._attr_entity_category = meta.category

        super().__init__(coordinator, f"data_{field.key}")

    @property
    def is_on(self) -> bool | None:
        """Return the current value from the latest device payload."""
        value = resolve_path(self.coordinator.device_data, self._path)
        return value if isinstance(value, bool) else None

class AwtrixBinarySensor(AwtrixEntity, BinarySensorEntity):
    """representation of a Awtrix binary sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: AwtrixCoordinator,
        key: str,
        name: str | None = None,
        icon: str | None = None
    ) -> None:
        """Initialize the binary sensor."""

        self.hass = hass
        self.key = key
        self._attr_name = name or key
        self._attr_is_on = False
        self._attr_icon = icon

        super().__init__(coordinator, key)
        self.coordinator.on_press(self.key, self.button_click)

    def button_click(self, state: str) -> None:
        """Set actual state."""
        self._attr_is_on = state == "1"
        self.async_write_ha_state()


    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh availability/device info; button state comes only from the webhook."""

        self.async_write_ha_state()
