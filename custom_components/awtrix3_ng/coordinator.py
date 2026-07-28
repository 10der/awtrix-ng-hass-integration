"""DataUpdateCoordinator for our integration."""

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .awtrix_ng_api import AwtrixNgApi, AwtrixNgApiError, AwtrixNgConnectionError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AwtrixCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """My Awtrix coordinator."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""

        # Set variables from values entered in config flow setup
        self.host = config_entry.data[CONF_HOST]
        self.user = config_entry.data[CONF_USERNAME]
        self.pwd = config_entry.data[CONF_PASSWORD]

        # set variables from options.  You need a default here in case options have not been set
        self.poll_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        # Initialise DataUpdateCoordinator
        super().__init__(
            hass,
            _LOGGER,
            name=f"{HOMEASSISTANT_DOMAIN} ({config_entry.unique_id})",
            # Method to call on every update interval.
            update_method=self.async_update_data,
            # Polling interval. Will only be polled if you have made your
            # platform entities, CoordinatorEntities.
            # Using config option here but you can just use a fixed value.
            update_interval=timedelta(seconds=self.poll_interval),
        )

        # Initialise your api here and make available to your integration.
        self.api = AwtrixNgApi(
            self.host,
            async_get_clientsession(hass),
            username=self.user or None,
            password=self.pwd or None,
            port=80,
        )
        self.on_button_click = {}

    async def async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint.

        This is the place to retrieve and pre-process the data into an appropriate data structure
        to be used to provide values for all your entities.
        """
        try:
            device, settings = await asyncio.gather(
                self.api.async_get_device(), self.api.async_get_settings()
            )
        except AwtrixNgConnectionError as err:
            _LOGGER.error(err)
            raise UpdateFailed(err) from err
        except AwtrixNgApiError as err:
            # This will show entities as unavailable by raising UpdateFailed exception
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        # What is returned here is stored in self.data by the DataUpdateCoordinator
        return {**device, **settings}

    def fire_event(
        self,
        args: dict[str, Any] | None = None,
    ):
        """Fire HA event."""

        event_name = f"{DOMAIN}_event"
        _LOGGER.debug("Firing event `%s` with arguments: %s", event_name, args)
        self.hass.bus.fire(
            event_name,
            args,
        )

    def on_press(self, key: str, action):
        """Set action on hardware button click."""
        self.on_button_click[key] = action

    def action_press(self, button, state):
        """On hardware button click."""
        # left middle right

        for btn in list(self.on_button_click.keys()):
            if f"button_{button}" == btn.replace("select", "middle"):
                self.on_button_click[btn](state)
