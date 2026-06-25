"""Diagnostics support for the NMA Mobile Credentials integration."""
from __future__ import annotations

from typing import Any, Dict

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from .const import CONF_BASE_URL, CONF_COMPANY_ID, DOMAIN
from .coordinator import NmaCoordinator

REDACT_DATA = {CONF_TOKEN}
REDACT_PEOPLE = {"email", "name"}
REDACT_CREDENTIAL = {"person"}
REDACT_COMPANY = {
    "tenantId",
    "billTo",
    "privacyOfficer",
    "soldTo",
    "incidentContact",
    "address",
    "identityProvider",
    "tciValue",
    "dfName",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Return diagnostics for a config entry (PII redacted)."""
    coordinator: NmaCoordinator = hass.data[DOMAIN][entry.entry_id]

    out: Dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(
                {
                    CONF_BASE_URL: entry.data.get(CONF_BASE_URL),
                    CONF_TOKEN: entry.data.get(CONF_TOKEN),
                    CONF_COMPANY_ID: entry.data.get(CONF_COMPANY_ID),
                },
                REDACT_DATA,
            ),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                str(coordinator.last_exception)
                if coordinator.last_exception
                else None
            ),
            "update_interval_s": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
        },
    }

    if coordinator.data is None:
        out["data"] = None
        return out

    company = coordinator.data.company.model_dump(by_alias=True, exclude_none=True)
    company = async_redact_data(company, REDACT_COMPANY)

    people = [
        async_redact_data(
            p.model_dump(by_alias=True, exclude_none=True), REDACT_PEOPLE
        )
        for p in coordinator.data.people
    ]

    credentials = [
        async_redact_data(
            c.model_dump(by_alias=True, exclude_none=True), REDACT_CREDENTIAL
        )
        for c in coordinator.data.credentials
    ]

    out["data"] = {
        "company": company,
        "people_total": coordinator.data.people_total,
        "credentials_total": coordinator.data.credentials_total,
        "fetched_at": coordinator.data.fetched_at.isoformat(),
        "duration_s": coordinator.data.duration_s,
        "people": people,
        "credentials": credentials,
    }
    return out
