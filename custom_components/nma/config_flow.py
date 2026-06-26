"""Config + options flow for NMA Mobile Credentials."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import NmaApi, NmaApiError
from .const import (
    CONF_BASE_URL,
    CONF_COMPANY_ID,
    CONF_VERIFY_SSL,
    DEFAULT_FETCH_CREDENTIALS,
    DEFAULT_FETCH_PEOPLE,
    DEFAULT_PAGE_SIZE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OPT_FETCH_CREDENTIALS,
    OPT_FETCH_PEOPLE,
    OPT_PAGE_SIZE,
    OPT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _user_schema(defaults: Optional[Dict[str, Any]] = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_BASE_URL, default=defaults.get(CONF_BASE_URL, "")
            ): str,
            vol.Required(
                CONF_TOKEN, default=defaults.get(CONF_TOKEN, "")
            ): str,
            vol.Required(
                CONF_COMPANY_ID, default=defaults.get(CONF_COMPANY_ID, "")
            ): str,
            vol.Optional(
                CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True)
            ): bool,
        }
    )


def _options_schema(entry: config_entries.ConfigEntry) -> vol.Schema:
    o = entry.options
    return vol.Schema(
        {
            vol.Optional(
                OPT_SCAN_INTERVAL,
                default=o.get(OPT_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(int, vol.Range(min=15, max=86400)),
            vol.Optional(
                OPT_PAGE_SIZE,
                default=o.get(OPT_PAGE_SIZE, DEFAULT_PAGE_SIZE),
            ): vol.All(int, vol.Range(min=1, max=500)),
            vol.Optional(
                OPT_FETCH_PEOPLE,
                default=o.get(OPT_FETCH_PEOPLE, DEFAULT_FETCH_PEOPLE),
            ): bool,
            vol.Optional(
                OPT_FETCH_CREDENTIALS,
                default=o.get(OPT_FETCH_CREDENTIALS, DEFAULT_FETCH_CREDENTIALS),
            ): bool,
        }
    )


class NmaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NMA Mobile Credentials."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        errors: Dict[str, str] = {}

        if user_input is not None:
            base_url = user_input[CONF_BASE_URL].strip().rstrip("/")
            token = user_input[CONF_TOKEN].strip()
            company_id_raw = user_input[CONF_COMPANY_ID].strip()
            verify_ssl = bool(user_input.get(CONF_VERIFY_SSL, True))

            try:
                UUID(company_id_raw)
            except ValueError:
                errors[CONF_COMPANY_ID] = "invalid_company_id"

            if not base_url.startswith(("http://", "https://")):
                errors[CONF_BASE_URL] = "invalid_url"

            if not errors:
                await self.async_set_unique_id(f"{base_url}:{company_id_raw}")
                self._abort_if_unique_id_configured()

                api = NmaApi(
                    base_url,
                    token,
                    company_id_raw,
                    page_size=1,  # cheap test fetch
                    verify_ssl=verify_ssl,
                )
                try:
                    company = await self.hass.async_add_executor_job(
                        api.fetch_company
                    )
                except NmaApiError as err:
                    _LOGGER.warning("NMA validation failed: %s", err)
                    if err.status_code in (401, 403):
                        errors["base"] = "invalid_auth"
                    elif err.status_code == 404:
                        errors[CONF_COMPANY_ID] = "company_not_found"
                    elif err.status_code in (502, 503, 504):
                        errors["base"] = "server_unavailable"
                    else:
                        errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error connecting to NMA API")
                    errors["base"] = "cannot_connect"
                else:
                    title = f"{company.name} ({company.type.value})"
                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_BASE_URL: base_url,
                            CONF_TOKEN: token,
                            CONF_COMPANY_ID: company_id_raw,
                            CONF_VERIFY_SSL: verify_ssl,
                        },
                        options={
                            OPT_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                            OPT_PAGE_SIZE: DEFAULT_PAGE_SIZE,
                            OPT_FETCH_PEOPLE: DEFAULT_FETCH_PEOPLE,
                            OPT_FETCH_CREDENTIALS: DEFAULT_FETCH_CREDENTIALS,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "NmaOptionsFlow":
        return NmaOptionsFlow(config_entry)


class NmaOptionsFlow(config_entries.OptionsFlow):
    """Options flow: scan interval, page size, what to fetch."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self.config_entry),
        )
