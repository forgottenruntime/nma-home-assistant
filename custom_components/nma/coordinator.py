"""DataUpdateCoordinator for the NMA Mobile Credentials integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NmaApi, NmaApiError, NmaSnapshot
from .const import (
    DEFAULT_FETCH_CREDENTIALS,
    DEFAULT_FETCH_PEOPLE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OPT_FETCH_CREDENTIALS,
    OPT_FETCH_PEOPLE,
    OPT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class NmaCoordinator(DataUpdateCoordinator[NmaSnapshot]):
    """Fetches a full snapshot of the NMA API on every poll."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: NmaApi,
    ) -> None:
        self.entry = entry
        self.api = api
        scan_interval = int(
            entry.options.get(OPT_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({api.company_id})",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> NmaSnapshot:
        include_people = bool(
            self.entry.options.get(OPT_FETCH_PEOPLE, DEFAULT_FETCH_PEOPLE)
        )
        include_credentials = bool(
            self.entry.options.get(OPT_FETCH_CREDENTIALS, DEFAULT_FETCH_CREDENTIALS)
        )
        try:
            return await self.hass.async_add_executor_job(
                lambda: self.api.fetch_all(
                    include_people=include_people,
                    include_credentials=include_credentials,
                )
            )
        except NmaApiError as err:
            raise UpdateFailed(f"NMA API error: {err}") from err
        except Exception as err:  # noqa: BLE001 - surface to HA
            raise UpdateFailed(f"Unexpected error: {err}") from err
