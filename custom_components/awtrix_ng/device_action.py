"""Provides device actions for AWTRIX NG."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, TemplateVarsType, VolDictType

from .const import DOMAIN, SERVICE_NOTIFY

ACTION_NOTIFY = "notify"
ACTION_DISMISS = "dismiss_notification"
CONF_MESSAGE = "message"
CONF_PAYLOAD = "payload"

NOTIFY_ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_TYPE): ACTION_NOTIFY,
        vol.Required(CONF_MESSAGE): cv.string,
        vol.Optional(CONF_PAYLOAD): dict,
    }
)

DISMISS_ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_TYPE): ACTION_DISMISS,
    }
)

ACTION_SCHEMA = vol.Any(NOTIFY_ACTION_SCHEMA, DISMISS_ACTION_SCHEMA)


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    return ACTION_SCHEMA(config)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for AWTRIX devices."""
    return [
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: ACTION_NOTIFY,
        },
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: ACTION_DISMISS,
        },
    ]


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""
    service_data: dict[str, Any] = {"message": ""}

    if config[CONF_TYPE] == ACTION_NOTIFY:
        service_data["message"] = config[CONF_MESSAGE]
        if payload := config.get(CONF_PAYLOAD):
            service_data["data"] = payload

    await hass.services.async_call(
        DOMAIN,
        SERVICE_NOTIFY,
        service_data,
        target={CONF_DEVICE_ID: config[CONF_DEVICE_ID]},
        blocking=True,
        context=context,
    )


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""
    if config[CONF_TYPE] != ACTION_NOTIFY:
        return {}

    fields: VolDictType = {
        vol.Required(CONF_MESSAGE): cv.string,
        vol.Optional(CONF_PAYLOAD): dict,
    }
    return {"extra_fields": vol.Schema(fields)}
