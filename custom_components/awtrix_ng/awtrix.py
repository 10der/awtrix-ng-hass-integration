"""Core components of AWTRIX Light."""

from collections.abc import Awaitable, Callable
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .awtrix_ng_api import AwtrixNgApi, AwtrixNgApiError
from .common import async_get_coordinator_by_device_id, getIcon
from .const import CONF_DEVICE_ID
from .coordinator import AwtrixCoordinator

_LOGGER = logging.getLogger(__name__)


class AwtrixService:
    """Allows to send updated to applications."""

    def __init__(self,
                 hass: HomeAssistant
                 ) -> None:
        """Initialize the device."""

        self.hass = hass

    def api(self, data: dict[str, Any]) -> list[AwtrixCoordinator]:
        """Create API on the fly."""
        result: list[AwtrixCoordinator] = []
        for device_id in data.get(CONF_DEVICE_ID, []):
            try:
                coordinator = async_get_coordinator_by_device_id(self.hass, device_id)
                result.append(coordinator)
            except Exception:  # noqa: BLE001
                _LOGGER.error("Failed to coordinator for %s", device_id)
        return result

    async def call(
        self,
        func: Callable[[AwtrixNgApi], Awaitable[Any]],
        seq: list[AwtrixCoordinator],
    ) -> dict[str, Any]:
        """Call action API."""
        result: list[dict[str | None, Any]] = []
        for i in seq:
            uniq_id = i.unique_id
            try:
                res =  await func(i.api)
                result.append({uniq_id: res})
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Failed to call %s: action: %s", i, err)
                result.append({uniq_id: False})

        return {"result" : result}

    async def push_app_data(self, data: dict[str, Any]) -> dict[str, Any]:
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

    async def switch_app(self, data: dict[str, Any]) -> dict[str, Any]:
        """Call API switch app."""

        app_id = data["name"]
        return await self.call(lambda x: x.async_set_active_app(app_id), self.api(data))

    async def settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """Call API settings."""

        data = data or {}
        payload = data.copy()
        payload.pop(CONF_DEVICE_ID, None)

        return await self.call(lambda x: x.async_update_settings(payload), self.api(data))

    async def get_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """Call API get settings."""
        return await self.call(lambda x: x.async_get_settings(), self.api(data))

    async def get_device(self, data: dict[str, Any]) -> dict[str, Any]:
        """Call API get device."""
        return await self.call(lambda x: x.async_get_device(), self.api(data))

    async def rtttl(self, data: dict[str, Any]) -> dict[str, Any]:
        """Play rtttl."""

        rtttl_data = data["rtttl"]
        return await self.call(lambda x: x.async_play_sound(rtttl=rtttl_data), self.api(data))

    async def sound(self, data: dict[str, Any]) -> dict[str, Any]:
        """Play rtttl sound."""

        sound_id = data["sound"]
        return await self.call(lambda x: x.async_play_sound(name=sound_id), self.api(data))

    async def overlay(self, data: dict[str, Any]) -> dict[str, Any]:
        """Set or clear the display overlay."""

        overlay_name = data.get("overlay")
        clear = data.get("clear", False)
        return await self.call(
            lambda x: x.async_update_display(overlay=overlay_name, clear_overlay=clear),
            self.api(data),
        )

    async def say(self, data: dict[str, Any]) -> dict[str, Any]:
        """Speak text with a Home Assistant TTS engine."""

        # tts needs its own requirements, imported only when the service is used
        from homeassistant.components.media_source import async_resolve_media  # noqa: PLC0415
        from homeassistant.components.tts.media_source import (  # noqa: PLC0415
            generate_media_source_id,
        )

        media_id = generate_media_source_id(
            self.hass,
            data["message"],
            data.get("engine"),
            data.get("language"),
            data.get("options"),
        )
        play_media = await async_resolve_media(self.hass, media_id, None)
        coordinators = self.api(data)
        url = await self._device_url(play_media.url, coordinators)
        return await self.call(lambda x: x.async_play_sound(file=url), coordinators)

    async def _device_url(self, url: str, coordinators: list[AwtrixCoordinator]) -> str:
        """Make a media URL reachable by the watch (internal URL, not external)."""

        from homeassistant.components.media_player.browse_media import (  # noqa: PLC0415
            async_process_play_media_url,
        )

        url = async_process_play_media_url(self.hass, url, allow_relative_url=True)
        if not url.startswith("/"):
            return url

        try:
            return get_url(self.hass, allow_external=False) + url
        except NoURLAvailableError:
            pass

        if coordinators:
            try:
                voice = await coordinators[0].api.async_get_voice()
            except AwtrixNgApiError as err:
                _LOGGER.debug("Cannot read voice config: %s", err)
            else:
                if base := (voice.get("config") or {}).get("url"):
                    return base.rstrip("/") + url

        _LOGGER.warning("No internal Home Assistant URL, the watch will use the external one")
        return get_url(self.hass) + url
