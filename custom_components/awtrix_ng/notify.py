"""Support for Awtrix notifications."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.notify import (  # type: ignore
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .common import (
    async_get_coordinator_by_device_id,
    async_get_coordinator_by_device_name,
    async_get_coordinator_devices,
    getIcon,
)
from .const import DOMAIN
from .coordinator import AwtrixCoordinator

_LOGGER = logging.getLogger(__name__)

ATTR_DATA = "data"
ATTR_TARGET = "target"


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

async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> BaseNotificationService | None:
    """Get the AWTRIX notification service."""

    if discovery_info is None:
        return None
    return AwtrixNotificationService(hass=hass)


########################################################################################################

PARALLEL_UPDATES = 1

class AwtrixNotificationService(BaseNotificationService):
    """Implement the notification service for Awtrix."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the notification service for Awtrix."""

        self.hass = hass

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to some Awtrix device."""

        data = dict(kwargs.get(ATTR_DATA) or {})
        device_ids = data.pop(ATTR_DEVICE_ID, None)
        target_ids = kwargs.get(ATTR_TARGET, "all")

        if device_ids is not None:
            if isinstance(device_ids, str):
                device_ids = [device_ids]
            coordinators = [
                async_get_coordinator_by_device_id(self.hass, device_id)
                for device_id in device_ids
            ]
        elif target_ids == "all":
            coordinators = async_get_coordinator_devices(self.hass)
        else:
            if isinstance(target_ids, str):
                target_ids = [target_ids]
            coordinators = async_get_coordinator_by_device_name(self.hass, target_ids)
        apis = [x.api for x in coordinators]

        for api in apis:
            await _async_send_to_api(self.hass, api, message, data=data)


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
