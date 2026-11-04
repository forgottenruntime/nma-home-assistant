"""Thin wrapper around the vendored NmaApiClient.

The wire client is synchronous (uses ``requests``). We expose a small set of
helpers that paginate fully and are intended to be invoked via
``hass.async_add_executor_job``.

All HTTP calls are routed through a sliding-window rate limiter so we stay
well under the server's global limit of 120 requests/minute (shared by every
API consumer).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple, TypeVar, Union

import requests

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

    def __init__(
        self, max_requests: int, period: float, stop: threading.Event
    ) -> None:
        self._max = max(1, max_requests)
        self._period = period
        self._calls: "deque[float]" = deque()
        self._lock = threading.Lock()
        self._stop = stop

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
                    self._stop.wait(sleep_for)  # returns early on close()
                self._evict(time.monotonic())
            self._calls.append(time.monotonic())

    def _evict(self, now: float) -> None:
        while self._calls and now - self._calls[0] >= self._period:
            self._calls.popleft()


def describe_error(err: BaseException) -> Tuple[Union[int, str], str]:
    """Short (code, text) for a failed API call, for attributes and alerts.

    HTTP errors keep their status code ("[502] Bad Gateway"); network errors
    get a word instead of requests' long "HTTPSConnectionPool(...)" text.
    """
    if isinstance(err, NmaApiError):
        return err.status_code, str(err)
    if isinstance(err, requests.Timeout):
        return "timeout", "No answer from the API in time (timeout)"
    if isinstance(err, requests.exceptions.SSLError):
        return "tls", "TLS/certificate error"
    if isinstance(err, requests.ConnectionError):
        text = str(err)
        if "NameResolution" in text or "Name or service not known" in text or "nodename" in text:
            return "dns", "Host name not found (DNS)"
        if "Connection refused" in text:
            return "refused", "Connection refused"
        return "connection", "Cannot connect to the API"
    return type(err).__name__, " ".join(str(err).split())[:120] or type(err).__name__


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
    # People/credentials come from a slower background sync; None until the
    # first one finished, so counts show "unknown" instead of a false 0.
    lists_synced_at: Optional[datetime] = None
    lists_duration_s: float = 0.0


@dataclass(slots=True)
class NmaLists:
    """Result of one people/credentials sync."""

    people: List[Person]
    people_total: int
    credentials: List[Credential]
    credentials_total: int
    requests: int


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
        self._stop = threading.Event()
        self._limiter = _RateLimiter(
            RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_PERIOD_S, self._stop
        )
        self._requests = 0

    def close(self) -> None:
        """Stop paging: a sync still running in a thread aborts at its next
        request, so a reload never doubles the load on the shared limit."""
        self._stop.set()

    def _throttled(self, fn: Callable[..., T], *args, **kwargs) -> T:
        """Run a client call after waiting for a rate-limit slot."""
        self._limiter.acquire()
        if self._stop.is_set():
            raise NmaApiError(0, message="stopped (entry unloaded)")
        self._requests += 1
        return fn(*args, **kwargs)

    # -- single fetches ---------------------------------------------------- #
    def fetch_company(self) -> Company:
        return self._throttled(self._client.get_company, self.company_id)

    def fetch_lists(
        self,
        *,
        include_people: bool = True,
        include_credentials: bool = True,
    ) -> NmaLists:
        """Fetch all pages of people and/or credentials."""
        before = self._requests
        people: List[Person] = []
        people_total = 0
        credentials: List[Credential] = []
        credentials_total = 0
        if include_people:
            people, people_total = self._fetch_people_all()
        if include_credentials:
            credentials, credentials_total = self._fetch_credentials_all()
        return NmaLists(
            people=people,
            people_total=people_total,
            credentials=credentials,
            credentials_total=credentials_total,
            requests=self._requests - before,
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


__all__ = ["NmaApi", "NmaApiError", "NmaLists", "NmaSnapshot", "describe_error"]
