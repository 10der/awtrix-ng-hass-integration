"""Async Python client for the AWTRIX NG HTTP API.

Designed for Home Assistant custom integrations. Pass Home Assistant's shared
``aiohttp.ClientSession`` (``async_get_clientsession(hass)``) to ``AwtrixNgApi``.

Generated from AWTRIX NG OpenAPI 1.0.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, TypeAlias
from urllib.parse import quote

from aiohttp import BasicAuth, ClientError, ClientResponse, ClientSession, FormData

JsonObject: TypeAlias = dict[str, Any]
JsonValue: TypeAlias = str | int | float | bool | None | JsonObject | list["JsonValue"]
Color: TypeAlias = int | str | Sequence[int] | tuple[str, int, int, int]
FileSource: TypeAlias = bytes | bytearray | memoryview | str | Path

DEFAULT_TIMEOUT: Final[float] = 10.0


@dataclass(slots=True, frozen=True)
class AwtrixNgErrorDetails:
    """Structured AWTRIX NG error response, when available."""

    error: str | None = None
    message: str | None = None
    field: str | None = None
    raw: JsonObject | None = None


class AwtrixNgApiError(Exception):
    """Base error raised by this client."""


class AwtrixNgConnectionError(AwtrixNgApiError):
    """The device could not be reached."""


class AwtrixNgTimeoutError(AwtrixNgConnectionError):
    """The request timed out."""


class AwtrixNgHttpError(AwtrixNgApiError):
    """The device returned a non-success HTTP response."""

    def __init__(
        self,
        status: int,
        reason: str,
        *,
        details: AwtrixNgErrorDetails | None = None,
        response_text: str | None = None,
    ) -> None:
        self.status = status
        self.reason = reason
        self.details = details
        self.response_text = response_text
        message = f"AWTRIX NG request failed: HTTP {status} {reason}"
        if details and (details.message or details.error):
            message += f": {details.message or details.error}"
        if details and details.field:
            message += f" (field: {details.field})"
        super().__init__(message)


class AwtrixNgAuthenticationError(AwtrixNgHttpError):
    """Authentication failed (HTTP 401)."""


class AwtrixNgNotFoundError(AwtrixNgHttpError):
    """A requested resource was not found (HTTP 404)."""


class AwtrixNgValidationError(AwtrixNgHttpError):
    """The request was rejected as invalid (HTTP 400/413/415/422)."""


class AwtrixNgApi:
    """Async AWTRIX NG API client."""

    def __init__(
        self,
        host: str,
        session: ClientSession,
        *,
        username: str | None = None,
        password: str | None = None,
        use_ssl: bool = False,
        port: int | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the client.

        ``host`` may be a hostname/IP (``awtrix.local``) or a complete base URL.
        The supplied aiohttp session is not closed by this client.
        """
        if not host or not host.strip():
            raise ValueError("host must not be empty")

        raw_host = host.strip().rstrip("/")
        if raw_host.startswith(("http://", "https://")):
            self._base_url = raw_host
        else:
            scheme = "https" if use_ssl else "http"
            port_part = f":{port}" if port is not None else ""
            self._base_url = f"{scheme}://{raw_host}{port_part}"

        if (username is None) != (password is None):
            raise ValueError("username and password must be supplied together")

        self._session = session
        self._auth = BasicAuth(username, password) if username is not None else None
        self._timeout = timeout

    @property
    def base_url(self) -> str:
        """Return the normalized device base URL."""
        return self._base_url

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: JsonValue | Mapping[str, Any] | Sequence[Any] | None = None,
        data: Any = None,
        headers: Mapping[str, str] | None = None,
        response_type: str = "json",
        timeout: float | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with self._session.request(
                method,
                url,
                params=params,
                json=json,
                data=data,
                headers=headers,
                auth=self._auth,
                timeout=self._timeout if timeout is None else timeout,
            ) as response:
                await self._raise_for_status(response)
                if response.status == 204 or response.content_length == 0:
                    return None
                if response_type == "bytes":
                    return await response.read()
                if response_type == "text":
                    return await response.text()
                if response_type == "none":
                    await response.read()
                    return None
                if "application/json" in response.headers.get("Content-Type", ""):
                    try:
                        return await response.json(content_type=None)
                    except (ValueError, TypeError) as err:
                        raise AwtrixNgApiError(
                            f"Malformed JSON response from {url}: {err}"
                        ) from err
                text = await response.text()
                if not text:
                    return None
                try:
                    return await response.json(content_type=None)
                except (ValueError, TypeError):
                    return text
        except TimeoutError as err:
            raise AwtrixNgTimeoutError(f"Timed out connecting to {url}") from err
        except ClientError as err:
            raise AwtrixNgConnectionError(f"Cannot connect to {url}: {err}") from err

    async def _raise_for_status(self, response: ClientResponse) -> None:
        if 200 <= response.status < 300:
            return

        text = await response.text()
        raw: JsonObject | None = None
        if text:
            try:
                parsed = await response.json(content_type=None)
                if isinstance(parsed, dict):
                    raw = parsed
            except (ValueError, TypeError):
                pass

        error_body = raw.get("error") if raw else None
        error_body = error_body if isinstance(error_body, dict) else {}
        details = AwtrixNgErrorDetails(
            error=_as_optional_str(error_body.get("code")),
            message=_as_optional_str(error_body.get("message")),
            field=_as_optional_str(error_body.get("field")),
            raw=raw,
        )
        kwargs = {
            "details": details,
            "response_text": text or None,
        }
        if response.status == 401:
            raise AwtrixNgAuthenticationError(response.status, response.reason, **kwargs)
        if response.status == 404:
            raise AwtrixNgNotFoundError(response.status, response.reason, **kwargs)
        if response.status in {400, 413, 415, 422}:
            raise AwtrixNgValidationError(response.status, response.reason, **kwargs)
        raise AwtrixNgHttpError(response.status, response.reason, **kwargs)

    # Device

    async def async_get_device(self) -> JsonObject:
        return await self._request("GET", "/api/v1/device")

    async def async_get_version(self) -> str:
        result = await self._request("GET", "/api/v1/version")
        if not isinstance(result, dict) or not isinstance(result.get("version"), str):
            raise AwtrixNgApiError("Invalid version response")
        return result["version"]

    async def async_reboot(self) -> None:
        await self._request("POST", "/api/v1/device/reboot", response_type="none")

    async def async_sleep(self, duration_ms: int) -> None:
        if duration_ms < 1:
            raise ValueError("duration_ms must be >= 1")
        await self._request(
            "POST", "/api/v1/device/sleep", json={"durationMs": duration_ms}, response_type="none"
        )

    async def async_factory_reset(self) -> None:
        await self._request("POST", "/api/v1/device/factory-reset", response_type="none")

    async def async_get_capabilities(self) -> JsonObject:
        return await self._request("GET", "/api/v1/capabilities")

    # Settings

    async def async_get_settings(self) -> JsonObject:
        return await self._request("GET", "/api/v1/settings")

    async def async_update_settings(self, settings: Mapping[str, Any]) -> JsonObject:
        return await self._request("PATCH", "/api/v1/settings", json=dict(settings))

    async def async_reset_settings(self) -> None:
        await self._request("POST", "/api/v1/settings/reset", response_type="none")

    # Display

    async def async_get_display(self) -> JsonObject:
        return await self._request("GET", "/api/v1/display")

    async def async_update_display(
        self,
        *,
        power: bool | None = None,
        overlay: str | None = None,
        overlay_settings: Mapping[str, Any] | None = None,
        clear_overlay: bool = False,
    ) -> None:
        payload: JsonObject = {}
        if power is not None:
            payload["power"] = power
        if clear_overlay:
            payload["overlay"] = None
        elif overlay is not None:
            payload["overlay"] = overlay
        if overlay_settings is not None:
            payload["overlaySettings"] = dict(overlay_settings)
        if not payload:
            raise ValueError("At least one display field must be supplied")
        await self._request("PATCH", "/api/v1/display", json=payload, response_type="none")

    async def async_set_moodlight(
        self,
        *,
        color: Color | None = None,
        kelvin: int | None = None,
        brightness: int | None = None,
    ) -> None:
        payload: JsonObject = {}
        if color is not None:
            payload["color"] = list(color) if isinstance(color, Sequence) and not isinstance(color, str) else color
        if kelvin is not None:
            if not 1000 <= kelvin <= 40000:
                raise ValueError("kelvin must be between 1000 and 40000")
            payload["kelvin"] = kelvin
        if brightness is not None:
            if not 0 <= brightness <= 255:
                raise ValueError("brightness must be between 0 and 255")
            payload["brightness"] = brightness
        if not payload:
            raise ValueError("At least one moodlight field must be supplied")
        await self._request("PUT", "/api/v1/display/moodlight", json=payload, response_type="none")

    async def async_disable_moodlight(self) -> None:
        await self._request("DELETE", "/api/v1/display/moodlight", response_type="none")

    async def async_get_screen(self) -> JsonObject:
        return await self._request("GET", "/api/v1/display/screen")

    # Apps

    async def async_get_apps(self) -> JsonObject | list[Any]:
        return await self._request("GET", "/api/v1/apps")

    async def async_set_active_app(self, name: str, *, fast: bool = False) -> None:
        await self._request(
            "PUT", "/api/v1/apps/active", json={"name": name, "fast": fast}, response_type="none"
        )

    async def async_next_app(self) -> None:
        await self._request("POST", "/api/v1/apps/next", response_type="none")

    async def async_previous_app(self) -> None:
        await self._request("POST", "/api/v1/apps/previous", response_type="none")

    async def async_set_app_order(self, order: Sequence[str]) -> None:
        await self._request("PUT", "/api/v1/apps/order", json={"order": list(order)}, response_type="none")

    async def async_push_app(self, name: str, payload: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> None:
        _validate_name(name, max_length=32)
        body: Any = dict(payload) if isinstance(payload, Mapping) else [dict(item) for item in payload]
        if not body:
            raise ValueError("A pushed app payload must not be empty")
        await self._request(
            "PUT", f"/api/v1/apps/pushed/{quote(name, safe='')}", json=body, response_type="none"
        )

    async def async_delete_app(self, name: str) -> JsonObject | None:
        _validate_name(name, max_length=32)
        return await self._request("DELETE", f"/api/v1/apps/{quote(name, safe='')}")

    # Notifications

    async def async_notify(self, payload: Mapping[str, Any]) -> None:
        await self._request("POST", "/api/v1/notifications", json=dict(payload), response_type="none")

    async def async_dismiss_notification(self) -> None:
        await self._request("DELETE", "/api/v1/notifications/active", response_type="none")

    async def async_dismiss_named_notification(self, name: str) -> JsonObject | None:
        return await self._request(
            "DELETE", f"/api/v1/notifications/{quote(name, safe='')}"
        )

    # Indicators

    async def async_set_indicator(
        self,
        indicator_id: int,
        *,
        color: Color | None = None,
        blink_ms: int | None = None,
        fade_ms: int | None = None,
    ) -> None:
        _validate_indicator_id(indicator_id)
        payload: JsonObject = {}
        if color is not None:
            payload["color"] = list(color) if isinstance(color, Sequence) and not isinstance(color, str) else color
        if blink_ms is not None:
            payload["blinkMs"] = blink_ms
        if fade_ms is not None:
            payload["fadeMs"] = fade_ms
        if not payload:
            raise ValueError("At least one indicator field must be supplied")
        await self._request(
            "PUT", f"/api/v1/indicators/{indicator_id}", json=payload, response_type="none"
        )

    async def async_clear_indicator(self, indicator_id: int) -> None:
        _validate_indicator_id(indicator_id)
        await self._request("DELETE", f"/api/v1/indicators/{indicator_id}", response_type="none")

    # Sounds

    async def async_get_sounds(self) -> JsonObject | list[Any]:
        return await self._request("GET", "/api/v1/sounds")

    async def async_save_sound(self, name: str, rtttl: str) -> None:
        _validate_name(name, max_length=24)
        await self._request(
            "PUT", f"/api/v1/sounds/{quote(name, safe='')}", json={"rtttl": rtttl}, response_type="none"
        )

    async def async_delete_sound(self, name: str) -> None:
        _validate_name(name, max_length=24)
        await self._request("DELETE", f"/api/v1/sounds/{quote(name, safe='')}", response_type="none")

    async def async_play_sound(
        self,
        *,
        name: str | None = None,
        rtttl: str | None = None,
        builtin: str | None = None,
    ) -> None:
        selected = sum(value is not None for value in (name, rtttl, builtin))
        if selected != 1:
            raise ValueError("Exactly one of name, rtttl or builtin must be supplied")
        payload = {key: value for key, value in {"name": name, "rtttl": rtttl, "builtin": builtin}.items() if value is not None}
        await self._request("POST", "/api/v1/sounds/play", json=payload, response_type="none")

    async def async_stop_sound(self) -> None:
        await self._request("POST", "/api/v1/sounds/stop", response_type="none")

    # Radio

    async def async_get_radio(self) -> JsonObject:
        return await self._request("GET", "/api/v1/radio")

    async def async_play_radio(self, station: str | int | Mapping[str, Any]) -> None:
        if isinstance(station, Mapping):
            payload = dict(station)
        elif isinstance(station, int):
            payload = {"index": station}
        else:
            payload = {"station": station}
        await self._request("POST", "/api/v1/radio/play", json=payload, response_type="none")

    async def async_stop_radio(self) -> None:
        await self._request("POST", "/api/v1/radio/stop", response_type="none")

    async def async_set_radio_stations(self, stations: Sequence[Mapping[str, Any]]) -> None:
        await self._request(
            "PUT", "/api/v1/radio/stations", json={"stations": [dict(s) for s in stations]}, response_type="none"
        )

    # Scripts

    async def async_get_script(self, name: str) -> str:
        _validate_name(name, max_length=32)
        return await self._request(
            "GET", f"/api/v1/apps/script/{quote(name, safe='')}", response_type="text"
        )

    async def async_install_script(self, name: str, source: str) -> JsonObject:
        _validate_name(name, max_length=32)
        return await self._request(
            "PUT",
            f"/api/v1/apps/script/{quote(name, safe='')}",
            data=source.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )

    async def async_get_shared_script_data(self) -> JsonObject:
        return await self._request("GET", "/api/v1/scripts/shared")

    # System

    async def async_get_system(self, *, include_secrets: bool = False) -> JsonObject:
        return await self._request(
            "GET", "/api/v1/system", params={"secrets": _bool_param(include_secrets)}
        )

    async def async_update_system(self, config: Mapping[str, Any]) -> JsonObject:
        return await self._request("PUT", "/api/v1/system", json=dict(config))

    async def async_wifi_scan(self) -> JsonObject | list[Any]:
        return await self._request("GET", "/api/v1/system/wifi-scan")

    async def async_get_logs(self, *, after: int | None = None) -> JsonObject:
        params = {"after": after} if after is not None else None
        return await self._request("GET", "/api/v1/logs", params=params)

    # Files and firmware

    async def async_list_files(self, directory: str = "/ICONS") -> JsonObject | list[Any]:
        return await self._request("GET", "/api/v1/files", params={"dir": directory})

    async def async_upload_file(
        self,
        file: FileSource,
        *,
        directory: str = "/ICONS",
        filename: str | None = None,
        content_type: str = "application/octet-stream",
    ) -> None:
        data, inferred_name = _read_file_source(file)
        form = FormData()
        form.add_field("file", data, filename=filename or inferred_name, content_type=content_type)
        await self._request("POST", "/api/v1/files", params={"dir": directory}, data=form, response_type="none")

    async def async_delete_file(self, path: str) -> None:
        await self._request("DELETE", "/api/v1/files", params={"path": path}, response_type="none")

    async def async_update_firmware(
        self,
        firmware: FileSource,
        *,
        filename: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        data, inferred_name = _read_file_source(firmware)
        form = FormData()
        form.add_field(
            "firmware", data, filename=filename or inferred_name, content_type="application/octet-stream"
        )
        await self._request("POST", "/update", data=form, response_type="none", timeout=timeout)

    async def async_restore_backup(
        self,
        archive: FileSource,
        *,
        filename: str | None = None,
        timeout: float = 120.0,
    ) -> JsonObject:
        data, inferred_name = _read_file_source(archive)
        form = FormData()
        form.add_field("file", data, filename=filename or inferred_name, content_type="application/zip")
        return await self._request("POST", "/api/v1/restore", data=form, timeout=timeout)


def _as_optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _bool_param(value: bool) -> str:
    return "true" if value else "false"


def _validate_indicator_id(indicator_id: int) -> None:
    if indicator_id not in {1, 2, 3}:
        raise ValueError("indicator_id must be 1, 2 or 3")


def _validate_name(name: str, *, max_length: int) -> None:
    if not name or len(name) > max_length:
        raise ValueError(f"name must contain 1..{max_length} characters")
    if not all(char.isalnum() or char in "_-" for char in name):
        raise ValueError("name may contain only letters, digits, '_' and '-'")


def _read_file_source(source: FileSource) -> tuple[bytes, str]:
    if isinstance(source, (bytes, bytearray, memoryview)):
        return bytes(source), "upload.bin"
    path = Path(source)
    return path.read_bytes(), path.name


__all__ = [
    "AwtrixNgApi",
    "AwtrixNgApiError",
    "AwtrixNgAuthenticationError",
    "AwtrixNgConnectionError",
    "AwtrixNgErrorDetails",
    "AwtrixNgHttpError",
    "AwtrixNgNotFoundError",
    "AwtrixNgTimeoutError",
    "AwtrixNgValidationError",
    "Color",
    "FileSource",
    "JsonObject",
]
