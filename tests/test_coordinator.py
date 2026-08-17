"""Tests for AwtrixCoordinator's availability handling.

Availability is what every entity in this integration relies on
(AwtrixEntity.available -> CoordinatorEntity.available -> coordinator.last_update_success),
so it's the first thing worth locking down with a test.
"""

from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.awtrix_ng.awtrix_ng_api import AwtrixNgConnectionError
from custom_components.awtrix_ng.const import DOMAIN
from custom_components.awtrix_ng.coordinator import AwtrixCoordinator

DEVICE_INFO = {"uid": "awtrix_test", "version": "1.0.0", "ipAddress": "192.0.2.10"}
SETTINGS_INFO = {"autoBrightness": True}


def _make_coordinator(hass: HomeAssistant) -> AwtrixCoordinator:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="awtrix_test",
        data={CONF_HOST: "192.0.2.10", CONF_USERNAME: "", CONF_PASSWORD: ""},
    )
    entry.add_to_hass(hass)
    return AwtrixCoordinator(hass, entry)


async def test_successful_refresh_is_available(hass: HomeAssistant) -> None:
    """A successful poll leaves the coordinator available with merged data."""
    coordinator = _make_coordinator(hass)

    with (
        patch.object(coordinator.api, "async_get_device", AsyncMock(return_value=DEVICE_INFO)),
        patch.object(coordinator.api, "async_get_settings", AsyncMock(return_value=SETTINGS_INFO)),
    ):
        await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data["uid"] == "awtrix_test"
    assert coordinator.data["autoBrightness"] is True


async def test_connection_error_marks_unavailable(hass: HomeAssistant) -> None:
    """A device that drops offline must flip last_update_success to False.

    This is the behaviour AwtrixEntity.available depends on - it used to be
    hard-coded to True regardless of the coordinator, so this test would have
    passed on the broken code too if it only checked the happy path above.
    """
    coordinator = _make_coordinator(hass)

    with (
        patch.object(coordinator.api, "async_get_device", AsyncMock(return_value=DEVICE_INFO)),
        patch.object(coordinator.api, "async_get_settings", AsyncMock(return_value=SETTINGS_INFO)),
    ):
        await coordinator.async_refresh()
    assert coordinator.last_update_success is True

    # async_update_data awaits both endpoints concurrently via asyncio.gather,
    # so async_get_settings must stay mocked too - otherwise it still fires a
    # real network call even though async_get_device fails first.
    with (
        patch.object(
            coordinator.api,
            "async_get_device",
            AsyncMock(side_effect=AwtrixNgConnectionError("device unreachable")),
        ),
        patch.object(coordinator.api, "async_get_settings", AsyncMock(return_value=SETTINGS_INFO)),
    ):
        await coordinator.async_refresh()

    assert coordinator.last_update_success is False
