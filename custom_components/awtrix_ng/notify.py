"""Support for Awtrix notifications."""

import logging
from typing import Any

from homeassistant.components.notify import BaseNotificationService  # type: ignore
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .common import (
    async_get_coordinator_by_device_name,
    async_get_coordinator_devices,
    getIcon,
)

_LOGGER = logging.getLogger(__name__)

ATTR_DATA = "data"
ATTR_TARGET = "target"

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

        target_ids = kwargs.get(ATTR_TARGET, 'all')
        if target_ids == 'all':
            coordinators = async_get_coordinator_devices(self.hass)
        else:
            coordinators = async_get_coordinator_by_device_name(self.hass, target_ids)
        apis = [x.api for x in coordinators]

        data = kwargs.get(ATTR_DATA)
        for api in apis:
            await self.notification(api, message, data)

    async def notification(self, api, message, data):
        """Handle the notification service for Awtrix."""

        data = data or {}
        msg = data.copy()
        msg["text"] = message

        if 'icon' in msg:
            if str(msg["icon"]).startswith(('http://', 'https://')):
                icon = await self.hass.async_add_executor_job(getIcon, str(msg["icon"]))
                if icon:
                    msg["icon"] = icon

        if not message:
            return await api.async_dismiss_notification()
        return await api.async_notify(msg)
