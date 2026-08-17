"""__init__.py: AWTRIX integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging

from aiohttp import web
from aiohttp.web_exceptions import HTTPException

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .common import async_get_coordinator_by_device_name
from .const import DOMAIN, PLATFORMS
from .coordinator import AwtrixCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

type MyConfigEntry = ConfigEntry[RuntimeData]

@dataclass
class RuntimeData:
    """Class to hold your data."""

    coordinator: DataUpdateCoordinator
    cancel_update_listener: Callable | None = None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Awtrix component."""

    # services
    await async_setup_services(hass)

    # webhook (buttons)
    await register_webhook_v2(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: MyConfigEntry) -> bool:
    """Set up Awtrix Integration from a config entry."""

    # Re-register services (a prior entry unload does not remove them, but
    # HA restart / first entry setup needs them registered here too).
    await async_setup_services(hass)

    coordinator = AwtrixCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    if not coordinator.data:
        raise ConfigEntryNotReady

    cancel_update_listener: Callable | None = config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )

    config_entry.runtime_data = RuntimeData(
        coordinator, cancel_update_listener)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # try:
    #     await register_webhook_v1(hass, config_entry)
    # except:
    #     _LOGGER.warning("Failed to register webhook v1, trying v2")

    # Return true to denote a successful setup.
    return True


async def _async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle config options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Delete device if selected from UI."""
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: MyConfigEntry) -> bool:
    """Unload a config entry."""

    # Services are shared across all config entries of this domain and are
    # re-registered in async_setup_entry, so they are kept registered here
    # to survive a reload of this entry.

    # Unload platforms and return result
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

async def register_webhook_v1(hass: HomeAssistant, config_entry):
    """Register webhook V1."""

    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        """Handle webhook callback.

        dev.json
        button_callback: http callback url for button presses.
        Sample http://hass.local:8123/api/webhook/awtrix_7c43d4
        TODO:
            - pass awtrix uid wia body automatically
            - remove awtrix uid from url
        """
        try:
            async with asyncio.timeout(5):
                data = dict(await request.post())
        except (TimeoutError, HTTPException) as error:
            _LOGGER.error("Could not get information from POST <%s>", error)
            return web.Response(text="ERR")
        device_name = webhook_id
        coordinators =  async_get_coordinator_by_device_name(hass, [device_name])
        coordinator = next(iter(coordinators), None)
        if coordinator is not None:
            button = data["button"]
            state = data["state"]
            coordinator.action_press(button, state)

        return web.Response(text="OK")

    # webhook.async_register(
    #     hass, DOMAIN, "Awtrix", config_entry.unique_id, handle_webhook
    # )

async def register_webhook_v2(hass: HomeAssistant):
    """Register webhook V2."""

    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        """Handle webhook callback.

        dev.json
        button_callback: http callback url for button presses.
        Sample http://hass.local:8123/api/webhook/awtrix
        TODO:
            - pass awtrix uid wia body automatically
            - remove awtrix uid from url
        """
        try:
            async with asyncio.timeout(5):
                data = dict(await request.post())
        except (TimeoutError, HTTPException) as error:
            _LOGGER.error("Could not get information from POST <%s>", error)
            return web.Response(text="ERR")

        if "button" not in data or "state" not in data:
            _LOGGER.error("Webhook payload missing button/state: %s", data)
            return web.Response(text="ERR")

        button = data["button"]
        state = data["state"]
        uid = str(data.get("uid"))
        if uid is not None:
            coordinators =  async_get_coordinator_by_device_name(hass, [uid])
            coordinator = next(iter(coordinators), None)
            if coordinator is not None:
                coordinator.action_press(button, state)

        return web.Response(text="OK")

    webhook.async_register(
        hass, DOMAIN, "Awtrix", "Awtrix-WebHook", handle_webhook
    )
