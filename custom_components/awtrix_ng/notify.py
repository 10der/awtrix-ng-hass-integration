"""Support for Awtrix notifications."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.notify import (  # type: ignore
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import getIcon
from .const import DOMAIN
from .coordinator import AwtrixCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AWTRIX notify entities from a config entry."""
    async_add_entities([AwtrixNotifyEntity(config_entry.runtime_data.coordinator)])


async def _async_send_to_api(
    hass: HomeAssistant,
    api: Any,
    message: str,
    title: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    """Send a notification payload to a single API instance."""

    payload = (data or {}).copy()
    payload.pop(ATTR_DEVICE_ID, None)

    if title:
        payload["title"] = title

    if "icon" in payload and str(payload["icon"]).startswith(("http://", "https://")):
        icon = await hass.async_add_executor_job(getIcon, str(payload["icon"]))
        if icon:
            payload["icon"] = icon

    if not message:
        await api.async_dismiss_notification()
        return

    payload["text"] = message
    await api.async_notify(payload)


PARALLEL_UPDATES = 1

class AwtrixNotifyEntity(NotifyEntity):
    """Per-device AWTRIX notify entity."""

    _attr_has_entity_name = True
    _attr_name = "Notifications"
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, coordinator: AwtrixCoordinator) -> None:
        """Initialize the notify entity."""
        self.coordinator = coordinator
        uid = coordinator.data["uid"]
        self._attr_unique_id = f"{uid}_notify"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uid)},
            name=uid,
            model="AWTRIX NG",
            sw_version=coordinator.data.get("version"),
            manufacturer="Blueforcer",
            configuration_url=f"http://{coordinator.data.get('ipAddress')}",
            suggested_area="Work Room",
        )

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Refresh availability whenever the coordinator updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_send_message(
        self, message: str, title: str | None = None
    ) -> None:
        """Send a standard notify message."""
        await _async_send_to_api(
            self.coordinator.hass,
            self.coordinator.api,
            message,
            title=title,
        )

    async def async_publish_message(
        self,
        message: str,
        title: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Send an AWTRIX notification with extended payload."""
        await _async_send_to_api(
            self.coordinator.hass,
            self.coordinator.api,
            message,
            title=title,
            data=data,
        )
