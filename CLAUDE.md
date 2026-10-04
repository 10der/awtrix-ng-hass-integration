# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Home Assistant custom integration (HACS) for **AWTRIX NG** (Blueforcer LED matrix firmware, not AWTRIX 3 — payload keys differ). Domain `awtrix_ng`, code in `custom_components/awtrix_ng/`. Version lives in `custom_components/awtrix_ng/manifest.json`. `iot_class: local_polling`.

## Commands

```bash
pip install -r requirements_test.txt        # pytest-homeassistant-custom-component, pytest-asyncio
pytest                                      # asyncio_mode=auto (pytest.ini)
pytest tests/test_coordinator.py::test_name # single test
```

Run from repo root. `tests/conftest.py` autouses `enable_custom_integrations`, required or HA says "Integration 'awtrix_ng' not found". No lint/build step locally; CI (`.github/workflows/validate.yml`) runs hassfest + HACS validation only.

The integration is also symlinked/copied into a live HA config (`/Users/olegdenisenko/Projects/hass/config/custom_components/awtrix_ng`, an additional working dir) — HA restart needed to pick up changes.

## Architecture

Two parallel control paths, both ending at the same API client:

- **Entities** (platforms in `const.PLATFORMS`: binary_sensor, button, light, notify, sensor, switch) — subclass `AwtrixEntity` (`entity.py`, a `CoordinatorEntity`) and read from `AwtrixCoordinator.data`.
- **Services** (`awtrix_ng.*`) — registered in `services.py`, driven by tables in `const.py` (`SERVICES`, `SERVICE_TO_SCHEMA`, `SERVICE_TO_FIELDS`, `SERVICE_TO_TARGET`). Each name in `SERVICES` is dispatched by `getattr` to the same-named method on `AwtrixService` (`awtrix.py`). **Adding a service = add name + schema + fields + target in `const.py`, plus a same-named method in `awtrix.py`.** `awtrix_ng.notify` is the exception: a platform entity service routed to `AwtrixNotifyEntity.async_publish_message` in `notify.py`.

Layers:
- `awtrix_ng_api.py` — standalone async HTTP client (`AwtrixNgApi`, typed `AwtrixNgApiError` hierarchy), generated from the AWTRIX NG OpenAPI spec. Takes HA's shared aiohttp session. Only place that knows HTTP routes.
- `coordinator.py` — `AwtrixCoordinator` per config entry; polls `async_get_device` + `async_get_settings` and merges them into one flat dict (`{**device, **settings}`). Also holds hardware button callbacks (`on_press` / `action_press`).
- `awtrix.py` — `AwtrixService`: resolves `device_id` targets to coordinators, fans out one call per device via `call()`, which swallows per-device errors and returns `{"result": [{uid: res | False}]}`.
- `common.py` — device/coordinator lookup helpers (by device_id, by name; filters registry on `manufacturer == "Blueforcer"`) and `getIcon` (blocking `requests` fetch; must run via `hass.async_add_executor_job`; http(s) icon URLs are converted to base64 JPEG before sending).
- `__init__.py` — `async_setup` registers services and one shared webhook `Awtrix-WebHook` for hardware button callbacks (device posts `button`, `state`, `uid`; routed to the coordinator by device name). Registration tolerates duplicates. `async_setup_entry` also re-registers services; unload intentionally keeps them. `register_webhook_v1` is dead code.
- `config_flow.py`, `strings.json` + `translations/` — UI config (host, user, password; scan interval option).

## Gotchas

- AWTRIX NG firmware rejects the whole request on unknown payload keys. In `awtrix_ng.notify` `data`, use `soundRtttl`, not `rtttl` (`rtttl` is only valid top-level for `awtrix_ng.rtttl`). Sound playback route is `/api/v1/audio/play`.
- Notify with empty `message` dismisses the current notification instead of sending.
- Services are shared across config entries, so don't unregister them on entry unload.

## Releases

Release = bump `manifest.json` version + commit + tag + push **and** `gh release create` (a tag alone is not a GitHub Release). No confirmation needed.
