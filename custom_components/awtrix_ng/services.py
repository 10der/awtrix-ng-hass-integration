"""Global services file."""

from functools import partial

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers.service import (
    async_register_platform_entity_service,
    async_set_service_schema,
)

from .awtrix import AwtrixService
from .const import (
    DOMAIN,
    SERVICE_NOTIFY,
    SERVICE_NOTIFY_FIELDS,
    SERVICE_NOTIFY_SCHEMA,
    SERVICE_PUSH_APP_DATA,
    SERVICE_TO_FIELDS,
    SERVICE_TO_SCHEMA,
    SERVICE_TO_TARGET,
    SERVICES,
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Handle Integration Services."""

    if not hass.services.has_service(DOMAIN, SERVICE_NOTIFY):
        async_register_platform_entity_service(
            hass,
            DOMAIN,
            SERVICE_NOTIFY,
            entity_domain="notify",
            func="async_publish_message",
            schema=SERVICE_NOTIFY_SCHEMA,
        )

        async_set_service_schema(
            hass,
            DOMAIN,
            SERVICE_NOTIFY,
            {
                "name": "Send AWTRIX notification",
                "description": "Send a notification to one or more AWTRIX NG notify entities.",
                "fields": SERVICE_NOTIFY_FIELDS,
                "target": {
                    "entity": {"domain": "notify", "integration": DOMAIN},
                    "device": {"integration": DOMAIN},
                },
            },
        )

    if hass.services.has_service(DOMAIN, SERVICE_PUSH_APP_DATA):
        return

    async def service_handler(awtrixService, service, call: ServiceCall) -> None:
        """Handle service call."""

        func = getattr(awtrixService, service)
        if func:
            return await func(call.data)
        return None

    awtrixService = AwtrixService(hass)
    for service_name in SERVICES:
        hass.services.async_register(
            DOMAIN,
            service_name,
            partial(service_handler, awtrixService, service_name),
            schema=SERVICE_TO_SCHEMA[service_name],
            supports_response=SupportsResponse.OPTIONAL
        )

        # Register the service description
        async_set_service_schema(
            hass,
            DOMAIN,
            service_name,
            {
                "description": (
                    f"Calls the service {service_name} of the node AWTRIX"
                ),
                "fields": SERVICE_TO_FIELDS[service_name],
                "target": SERVICE_TO_TARGET[service_name],
            },
        )
