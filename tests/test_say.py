"""Tests for the awtrix_ng.say service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.components.media_source import PlayMedia
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.network import NoURLAvailableError

from custom_components.awtrix_ng.awtrix import AwtrixService
from custom_components.awtrix_ng.awtrix_ng_api import AwtrixNgConnectionError
from custom_components.awtrix_ng.const import SERVICE_SAY_SCHEMA

INTERNAL_URL = "http://192.168.88.10:8123"
MEDIA_ID = "media-source://tts/tts.openai_tts?message=Hi"
TTS_PATH = "/api/tts_proxy/abc.mp3"
SIGNED_PATH = "/api/tts_proxy/abc.mp3?authSig=1"


def _coordinator(uid: str, voice: dict | Exception | None = None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.unique_id = uid
    coordinator.api.async_play_sound = AsyncMock()
    if isinstance(voice, Exception):
        coordinator.api.async_get_voice = AsyncMock(side_effect=voice)
    else:
        coordinator.api.async_get_voice = AsyncMock(return_value=voice or {})
    return coordinator


@pytest.fixture
def generate() -> MagicMock:
    with patch(
        "homeassistant.components.tts.media_source.generate_media_source_id", return_value=MEDIA_ID
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def resolve() -> AsyncMock:
    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        AsyncMock(return_value=PlayMedia(url=TTS_PATH, mime_type="audio/mpeg")),
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def sign() -> MagicMock:
    with patch(
        "homeassistant.components.media_player.browse_media.async_process_play_media_url",
        return_value=SIGNED_PATH,
    ) as mock:
        yield mock


@pytest.fixture
def internal_url() -> MagicMock:
    def get_url(hass, *, allow_external=True, **kwargs):
        if allow_external:
            return "https://external.example.com"
        return INTERNAL_URL

    with patch("custom_components.awtrix_ng.awtrix.get_url", side_effect=get_url) as mock:
        yield mock


def _service(hass: HomeAssistant, *coordinators: MagicMock) -> AwtrixService:
    service = AwtrixService(hass)
    service.api = MagicMock(return_value=list(coordinators))
    return service


async def test_say_sends_file_url(
    hass: HomeAssistant, generate: MagicMock, internal_url: MagicMock
) -> None:
    """The signed TTS path is prefixed with the internal URL and sent as file."""
    clock = _coordinator("a")

    await _service(hass, clock).say({"device_id": ["a"], "message": "Hi"})

    clock.api.async_play_sound.assert_awaited_once_with(file=INTERNAL_URL + SIGNED_PATH)


async def test_say_passes_engine_language_options(
    hass: HomeAssistant, generate: MagicMock, internal_url: MagicMock
) -> None:
    """Engine, language and options reach the TTS media source generator."""
    await _service(hass, _coordinator("a")).say(
        {
            "device_id": ["a"],
            "message": "Привіт",
            "engine": "tts.openai_tts",
            "language": "uk",
            "options": {"voice": "alloy"},
        }
    )

    generate.assert_called_once_with(
        hass, "Привіт", "tts.openai_tts", "uk", {"voice": "alloy"}
    )


async def test_say_without_internal_url_uses_watch_config_url(
    hass: HomeAssistant, generate: MagicMock
) -> None:
    """Without an internal URL the HA address configured on the watch is used."""
    clock = _coordinator("a", {"config": {"url": INTERNAL_URL}})

    def get_url(hass, *, allow_external=True, **kwargs):
        if allow_external:
            return "https://external.example.com"
        raise NoURLAvailableError

    with patch("custom_components.awtrix_ng.awtrix.get_url", side_effect=get_url):
        await _service(hass, clock).say({"device_id": ["a"], "message": "Hi"})

    clock.api.async_play_sound.assert_awaited_once_with(file=INTERNAL_URL + SIGNED_PATH)


@pytest.mark.parametrize(
    "voice",
    [
        pytest.param(AwtrixNgConnectionError("down"), id="voice-unavailable"),
        pytest.param({}, id="voice-without-url"),
    ],
)
async def test_say_voice_lookup_falls_back_to_get_url(
    hass: HomeAssistant, generate: MagicMock, voice: dict | Exception
) -> None:
    """When the watch gives no URL, the HA default URL is used."""
    clock = _coordinator("a", voice)

    def get_url(hass, *, allow_external=True, **kwargs):
        if allow_external:
            return "https://external.example.com"
        raise NoURLAvailableError

    with patch("custom_components.awtrix_ng.awtrix.get_url", side_effect=get_url):
        await _service(hass, clock).say({"device_id": ["a"], "message": "Hi"})

    clock.api.async_play_sound.assert_awaited_once_with(
        file="https://external.example.com" + SIGNED_PATH
    )


async def test_say_no_engine_raises(hass: HomeAssistant) -> None:
    """A missing TTS engine surfaces as ServiceValidationError, nothing is played."""
    clock = _coordinator("a")

    with (
        patch(
            "homeassistant.components.tts.media_source.generate_media_source_id",
            side_effect=ServiceValidationError("no engine"),
        ),
        pytest.raises(ServiceValidationError),
    ):
        await _service(hass, clock).say({"device_id": ["a"], "message": "Hi"})

    clock.api.async_play_sound.assert_not_awaited()


async def test_say_generates_once_for_many_devices(
    hass: HomeAssistant,
    generate: MagicMock,
    resolve: AsyncMock,
    internal_url: MagicMock,
) -> None:
    """The mp3 is produced once and played on every watch."""
    first, second = _coordinator("a"), _coordinator("b")

    await _service(hass, first, second).say({"device_id": ["a", "b"], "message": "Hi"})

    generate.assert_called_once()
    resolve.assert_awaited_once()
    first.api.async_play_sound.assert_awaited_once()
    second.api.async_play_sound.assert_awaited_once()


async def test_say_schema_rejects_non_dict_options() -> None:
    """options must be a mapping."""
    with pytest.raises(vol.Invalid):
        SERVICE_SAY_SCHEMA({"device_id": ["x"], "message": "hi", "options": "no"})
