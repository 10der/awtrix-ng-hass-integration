"""Core components of AWTRIX Light."""

import logging

from homeassistant.core import HomeAssistant

from .common import async_get_coordinator_by_device_id, getIcon
from .const import CONF_DEVICE_ID

_LOGGER = logging.getLogger(__name__)


class AwtrixService:
    """Allows to send updated to applications."""

    def __init__(self,
                 hass: HomeAssistant
                 ) -> None:
        """Initialize the device."""

        self.hass = hass

    def api(self, data):
        """Create API on the fly."""
        result = []
        for device_id in data.get(CONF_DEVICE_ID):
            try:
                coordinator = async_get_coordinator_by_device_id(self.hass, device_id)
                result.append(coordinator)
            except Exception:  # noqa: BLE001
                _LOGGER.error("Failed to coordinator for %s", device_id)
        return result

    async def call(self, func, seq):
        """Call action API."""
        result = []
        for i in seq:
            uniq_id = i.config_entry.unique_id
            try:
                res =  await func(i.api)
                result.append({uniq_id: res})
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Failed to call %s: action: %s", i, err)
                result.append({uniq_id: False})

        return {"result" : result}

    async def push_app_data(self, data):
        """Update the application data."""

        app_id = data["name"]

        action_data = data.get("data", {}) or {}
        payload = action_data.copy()
        payload.pop(CONF_DEVICE_ID, None)

        if not payload:
            return await self.call(lambda x: x.async_delete_app(app_id), self.api(data))

        if 'icon' in payload:
            if str(payload["icon"]).startswith(('http://', 'https://')):
                payload["icon"] = await self.hass.async_add_executor_job(getIcon, str(payload["icon"]))

        return await self.call(lambda x: x.async_push_app(app_id, payload), self.api(data))

    async def switch_app(self, data):
        """Call API switch app."""

        app_id = data["name"]
        return await self.call(lambda x: x.async_set_active_app(app_id), self.api(data))

    async def settings(self, data):
        """Call API settings."""

        data = data or {}
        payload = data.copy()
        payload.pop(CONF_DEVICE_ID, None)

        return await self.call(lambda x: x.async_update_settings(payload), self.api(data))

    async def get_settings(self, data):
        """Call API get settings."""
        return await self.call(lambda x: x.async_get_settings(), self.api(data))

    async def get_device(self, data):
        """Call API get device."""
        return await self.call(lambda x: x.async_get_device(), self.api(data))

    async def rtttl(self, data):
        """Play rtttl."""

        rtttl_data = data["rtttl"]
        return await self.call(lambda x: x.async_play_sound(rtttl=rtttl_data), self.api(data))

    async def sound(self, data):
        """Play rtttl sound."""

        sound_id = data["sound"]
        return await self.call(lambda x: x.async_play_sound(name=sound_id), self.api(data))

    async def overlay(self, data):
        """Set or clear the display overlay."""

        overlay_name = data.get("overlay")
        clear = data.get("clear", False)
        return await self.call(
            lambda x: x.async_update_display(overlay=overlay_name, clear_overlay=clear),
            self.api(data),
        )
