"""NMA Mobile Credentials integration for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .api import NmaApi
from .const import (
    ATTR_ENTRY_ID,
    CONF_BASE_URL,
    CONF_COMPANY_ID,
    CONF_VERIFY_SSL,
    DEFAULT_PAGE_SIZE,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MANUFACTURER,
    MAX_PAGE_SIZE,
    MODEL,
    OPT_PAGE_SIZE,
    PLATFORMS,
    SERVICE_REFRESH,
)
from .coordinator import NmaCoordinator

_LOGGER = logging.getLogger(__name__)

REFRESH_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): str,
    }
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """No YAML configuration — UI only. Register services once."""
    hass.data.setdefault(DOMAIN, {})

    async def _handle_refresh(call: ServiceCall) -> None:
        entry_id = call.data.get(ATTR_ENTRY_ID)
        coordinators: list[NmaCoordinator] = []
        if entry_id:
            coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
            if coordinator is None:
                raise HomeAssistantError(
                    f"No NMA config entry with id {entry_id}"
                )
            coordinators = [coordinator]
        else:
            coordinators = [
                c for c in hass.data.get(DOMAIN, {}).values()
                if isinstance(c, NmaCoordinator)
            ]
        for coordinator in coordinators:
            await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, _handle_refresh, schema=REFRESH_SCHEMA
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    hass.data.setdefault(DOMAIN, {})

    page_size = int(entry.options.get(OPT_PAGE_SIZE, DEFAULT_PAGE_SIZE))
    # Clamp to the API's recommended maximum (handles legacy entries that
    # stored a larger value before this cap existed).
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    api = NmaApi(
        base_url=entry.data[CONF_BASE_URL],
        token=entry.data.get(CONF_TOKEN),
        company_id=entry.data[CONF_COMPANY_ID],
        page_size=page_size,
        timeout=DEFAULT_TIMEOUT,
        verify_ssl=bool(entry.data.get(CONF_VERIFY_SSL, True)),
    )

    coordinator = NmaCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register the company device early so the UI shows it cleanly.
    device_registry = dr.async_get(hass)
    if coordinator.data:
        company = coordinator.data.company
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, str(api.company_id))},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=company.name,
            configuration_url=api._client.base_url,  # noqa: SLF001
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
