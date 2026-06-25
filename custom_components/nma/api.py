"""Thin wrapper around the vendored NmaApiClient.

The wire client is synchronous (uses ``requests``). We expose a small set of
helpers that paginate fully and are intended to be invoked via
``hass.async_add_executor_job``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from .nma_api import NmaApiClient, NmaApiError
from .nma_api.models import Company, Credential, Person


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
        page_size: int = 100,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ) -> None:
        self._client = NmaApiClient(base_url, token=token, timeout=timeout)
        # ``requests.Session`` is held by the vendored client.
        self._client._session.verify = verify_ssl  # noqa: SLF001
        self.company_id = company_id
        self.page_size = page_size

    # -- single fetches ---------------------------------------------------- #
    def fetch_company(self) -> Company:
        return self._client.get_company(self.company_id)

    def fetch_all(
        self,
        *,
        include_people: bool = True,
        include_credentials: bool = True,
    ) -> NmaSnapshot:
        """Fetch company + (optionally) all people and credentials."""
        start = datetime.now(timezone.utc)
        company = self._client.get_company(self.company_id)
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
            res = self._client.get_people(
                self.company_id, page=page, size=self.page_size
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
            res = self._client.get_credentials(
                self.company_id, page=page, size=self.page_size
            )
            items.extend(res.items)
            total = res.page_info.total_elements
            if (page + 1) >= max(res.page_info.total_pages, 1) or not res.items:
                break
            page += 1
        return items, total


__all__ = ["NmaApi", "NmaApiError", "NmaSnapshot"]
