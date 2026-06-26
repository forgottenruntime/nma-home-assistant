"""Thin wrapper around the vendored NmaApiClient.

The wire client is synchronous (uses ``requests``). We expose a small set of
helpers that paginate fully and are intended to be invoked via
``hass.async_add_executor_job``.

All HTTP calls are routed through a sliding-window rate limiter so we stay
under the server's documented limit of 30 requests/minute (across all
endpoints and environments).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional, TypeVar

from .const import RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_PERIOD_S
from .nma_api import NmaApiClient, NmaApiError
from .nma_api.models import Company, Credential, Person

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class _RateLimiter:
    """Thread-safe sliding-window rate limiter.

    Allows at most ``max_requests`` calls within any ``period`` seconds. When
    the window is full, :meth:`acquire` blocks (``time.sleep``) until the
    oldest call ages out. Safe to call from an executor thread — never from the
    event loop.
    """

    def __init__(self, max_requests: int, period: float) -> None:
        self._max = max(1, max_requests)
        self._period = period
        self._calls: "deque[float]" = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            self._evict(now)
            if len(self._calls) >= self._max:
                sleep_for = self._period - (now - self._calls[0])
                if sleep_for > 0:
                    _LOGGER.debug(
                        "NMA rate limit reached (%d/%ds); sleeping %.2fs",
                        self._max,
                        int(self._period),
                        sleep_for,
                    )
                    time.sleep(sleep_for)
                self._evict(time.monotonic())
            self._calls.append(time.monotonic())

    def _evict(self, now: float) -> None:
        while self._calls and now - self._calls[0] >= self._period:
            self._calls.popleft()


@dataclass(slots=True)
class NmaSnapshot:
    """Single coordinator update snapshot."""

    company: Company
    people: List[Person] = field(default_factory=list)
    credentials: List[Credential] = field(default_factory=list)
    people_total: int = 0
    credentials_total: int = 0
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_s: float = 0.0


class NmaApi:
    """Sync helper. Call methods only from an executor thread."""

    def __init__(
        self,
        base_url: str,
        token: Optional[str],
        company_id: str,
        *,
        page_size: int = 50,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ) -> None:
        self._client = NmaApiClient(base_url, token=token, timeout=timeout)
        # ``requests.Session`` is held by the vendored client.
        self._client._session.verify = verify_ssl  # noqa: SLF001
        self.company_id = company_id
        self.page_size = page_size
        self._limiter = _RateLimiter(RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_PERIOD_S)

    def _throttled(self, fn: Callable[..., T], *args, **kwargs) -> T:
        """Run a client call after waiting for a rate-limit slot."""
        self._limiter.acquire()
        return fn(*args, **kwargs)

    # -- single fetches ---------------------------------------------------- #
    def fetch_company(self) -> Company:
        return self._throttled(self._client.get_company, self.company_id)

    def fetch_all(
        self,
        *,
        include_people: bool = True,
        include_credentials: bool = True,
    ) -> NmaSnapshot:
        """Fetch company + (optionally) all people and credentials."""
        start = datetime.now(timezone.utc)
        company = self._throttled(self._client.get_company, self.company_id)
        people: List[Person] = []
        people_total = 0
        credentials: List[Credential] = []
        credentials_total = 0

        if include_people:
            people, people_total = self._fetch_people_all()
        if include_credentials:
            credentials, credentials_total = self._fetch_credentials_all()

        end = datetime.now(timezone.utc)
        return NmaSnapshot(
            company=company,
            people=people,
            credentials=credentials,
            people_total=people_total,
            credentials_total=credentials_total,
            fetched_at=end,
            duration_s=(end - start).total_seconds(),
        )

    # -- paginated fetches ------------------------------------------------- #
    def _fetch_people_all(self):
        items: List[Person] = []
        page = 0
        total = 0
        while True:
            res = self._throttled(
                self._client.get_people,
                self.company_id,
                page=page,
                size=self.page_size,
            )
            items.extend(res.items)
            total = res.page_info.total_elements
            if (page + 1) >= max(res.page_info.total_pages, 1) or not res.items:
                break
            page += 1
        return items, total

    def _fetch_credentials_all(self):
        items: List[Credential] = []
        page = 0
        total = 0
        while True:
            res = self._throttled(
                self._client.get_credentials,
                self.company_id,
                page=page,
                size=self.page_size,
            )
            items.extend(res.items)
            total = res.page_info.total_elements
            if (page + 1) >= max(res.page_info.total_pages, 1) or not res.items:
                break
            page += 1
        return items, total


__all__ = ["NmaApi", "NmaApiError", "NmaSnapshot"]
