"""DataUpdateCoordinator for the NMA Mobile Credentials integration."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NmaApi, NmaLists, NmaSnapshot, describe_error
from .const import (
    DEFAULT_FETCH_CREDENTIALS,
    DEFAULT_FETCH_PEOPLE,
    DEFAULT_PERSONAL_DATA,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LIST_SYNC_REQUESTS_PER_MIN,
    LIST_SYNC_RETRY_S,
    OPT_FETCH_CREDENTIALS,
    OPT_FETCH_PEOPLE,
    OPT_PERSONAL_DATA,
    OPT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class NmaCoordinator(DataUpdateCoordinator[NmaSnapshot]):
    """Polls the company every interval; syncs people/credentials in the
    background, paced to a small share of the API's global rate limit.

    A big company needs minutes to page through, so the sync never blocks
    setup (Home Assistant cancels a setup after 300 s) or the health poll.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: NmaApi,
    ) -> None:
        self.entry = entry
        self.api = api
        # Fixed for the entry's lifetime: changing options reloads the entry.
        self.personal_data = bool(
            entry.options.get(OPT_PERSONAL_DATA, DEFAULT_PERSONAL_DATA)
        )
        self._include_people = bool(
            entry.options.get(OPT_FETCH_PEOPLE, DEFAULT_FETCH_PEOPLE)
        )
        self._include_credentials = bool(
            entry.options.get(OPT_FETCH_CREDENTIALS, DEFAULT_FETCH_CREDENTIALS)
        )
        self._lists: Optional[NmaLists] = None
        self._lists_synced_at: Optional[datetime] = None
        self._lists_duration_s = 0.0
        self._sync_running = False
        self._next_sync = 0.0  # time.monotonic() deadline
        # Code of the last failed health poll (HTTP status or a word such as
        # "timeout"); None while the API answers. Shown on api_reachable.
        self.error_code = None
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
        start = datetime.now(timezone.utc)
        try:
            company = await self.hass.async_add_executor_job(
                self.api.fetch_company
            )
        except Exception as err:  # noqa: BLE001 - surface to HA
            self.error_code, text = describe_error(err)
            if not self.last_update_success:
                # HA skips entity updates on a second failure in a row; push
                # one anyway so api_reachable shows the current error.
                self.hass.loop.call_soon(self.async_update_listeners)
            raise UpdateFailed(text) from err
        self.error_code = None
        end = datetime.now(timezone.utc)

        if not self._sync_running and time.monotonic() >= self._next_sync:
            self._sync_running = True
            self.entry.async_create_background_task(
                self.hass, self._async_sync_lists(), name=f"{self.name} sync"
            )

        return self._with_lists(
            NmaSnapshot(
                company=company,
                fetched_at=end,
                duration_s=(end - start).total_seconds(),
            )
        )

    def _with_lists(self, snapshot: NmaSnapshot) -> NmaSnapshot:
        lists = self._lists
        if lists is None:
            return snapshot
        return dataclasses.replace(
            snapshot,
            people=lists.people,
            people_total=lists.people_total,
            credentials=lists.credentials,
            credentials_total=lists.credentials_total,
            lists_synced_at=self._lists_synced_at,
            lists_duration_s=self._lists_duration_s,
        )

    async def _async_sync_lists(self) -> None:
        start = time.monotonic()
        try:
            lists = await self.hass.async_add_executor_job(
                lambda: self.api.fetch_lists(
                    include_people=self._include_people,
                    include_credentials=self._include_credentials,
                )
            )
        except Exception as err:  # noqa: BLE001 - keep last data, retry later
            _LOGGER.warning(
                "NMA people/credentials sync failed, retrying in %d s: %s",
                LIST_SYNC_RETRY_S,
                describe_error(err)[1],
            )
            self._next_sync = time.monotonic() + LIST_SYNC_RETRY_S
            return
        finally:
            self._sync_running = False

        duration = time.monotonic() - start
        # ponytail: average pacing only; a delta endpoint would beat re-paging.
        self._next_sync = start + max(
            duration, lists.requests * 60 / LIST_SYNC_REQUESTS_PER_MIN
        )
        self._lists = lists
        self._lists_synced_at = datetime.now(timezone.utc)
        self._lists_duration_s = duration
        _LOGGER.debug(
            "NMA sync: %d people, %d credentials, %d requests in %.1f s",
            lists.people_total,
            lists.credentials_total,
            lists.requests,
            duration,
        )
        if self.data is not None:
            self.async_set_updated_data(self._with_lists(self.data))
