"""Tests for AwtrixNgApi audio and voice calls."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.awtrix_ng.awtrix_ng_api import AwtrixNgApi


@pytest.fixture
def api() -> AwtrixNgApi:
    """Client with a mocked transport."""
    client = AwtrixNgApi("192.168.0.1", MagicMock())
    client._request = AsyncMock(return_value=None)
    return client


async def test_play_sound_file_payload(api: AwtrixNgApi) -> None:
    """A file URL is sent as the only payload key."""
    await api.async_play_sound(file="http://x/a.mp3")

    api._request.assert_awaited_once_with(
        "POST", "/api/v1/audio/play", json={"file": "http://x/a.mp3"}, response_type="none"
    )


async def test_play_sound_rejects_multiple(api: AwtrixNgApi) -> None:
    """File together with another selector is rejected."""
    with pytest.raises(ValueError):
        await api.async_play_sound(file="http://x/a.mp3", name="beep")


async def test_get_voice(api: AwtrixNgApi) -> None:
    """Voice config is read from /api/v1/voice."""
    api._request.return_value = {"config": {"url": "http://ha:8123"}}

    assert await api.async_get_voice() == {"config": {"url": "http://ha:8123"}}
    api._request.assert_awaited_once_with("GET", "/api/v1/voice")
