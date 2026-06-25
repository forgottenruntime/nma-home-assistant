"""A small, typed Python client for the NMA API (mobile credentials).

Example
-------
>>> from nma_api import NmaApiClient
>>> client = NmaApiClient("https://dev.api.example.com", token="...")
>>> company = client.get_company("00000000-0000-0000-0000-000000000000")
>>> people = client.get_people(company.id, page=0, size=20, name="jane")
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Sequence, Union
from uuid import UUID

import requests

from .models import (
    Company,
    CredentialsPaged,
    Error,
    PeoplePaged,
    Platform,
    SortDirection,
    SortFieldCredential,
    SortFieldPerson,
    UapMigrationStatus,
)

CompanyId = Union[str, UUID]


class NmaApiError(Exception):
    """Raised when the API returns a non-2xx response."""

    def __init__(
        self,
        status_code: int,
        error: Optional[Error] = None,
        message: Optional[str] = None,
    ) -> None:
        self.status_code = status_code
        self.error = error
        text = message or (error.message if error else f"HTTP {status_code}")
        super().__init__(f"[{status_code}] {text}")

    @classmethod
    def from_response(cls, response: "requests.Response") -> "NmaApiError":
        error: Optional[Error] = None
        try:
            error = Error.model_validate(response.json())
        except Exception:  # noqa: BLE001 - body may not be JSON / Error-shaped
            error = None
        message = error.message if error else (response.text or "")[:500]
        return cls(response.status_code, error, message)


def _scalar(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _clean_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Drop ``None`` values and normalise enums / datetimes / lists."""
    cleaned: Dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            items = [_scalar(v) for v in value]
            if items:
                cleaned[key] = items
        else:
            cleaned[key] = _scalar(value)
    return cleaned


class NmaApiClient:
    """Thin, typed wrapper around the NMA admin endpoints."""

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        *,
        session: Optional[requests.Session] = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.setdefault("Accept", "application/json")
        if token:
            self._session.headers["Authorization"] = f"Bearer {token}"

    # -- internal ----------------------------------------------------------- #
    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        response = self._session.get(
            f"{self.base_url}{path}",
            params=_clean_params(params or {}),
            timeout=self.timeout,
        )
        if not response.ok:
            raise NmaApiError.from_response(response)
        return response.json()

    # -- endpoints ---------------------------------------------------------- #
    def get_company(self, company_id: CompanyId) -> Company:
        """GET /api/admin/companies/{id}"""
        data = self._get(f"/api/admin/companies/{company_id}")
        return Company.model_validate(data)

    def get_people(
        self,
        company_id: CompanyId,
        *,
        page: int = 0,
        size: Optional[int] = None,
        statuses: Optional[Sequence[str]] = None,
        name: Optional[str] = None,
        email: Optional[str] = None,
        platforms: Optional[Sequence[Union[str, Platform]]] = None,
        uap_migration_statuses: Optional[Sequence[Union[str, UapMigrationStatus]]] = None,
        credential_count: Optional[int] = None,
        creation_date_from: Optional[Union[str, datetime]] = None,
        creation_date_to: Optional[Union[str, datetime]] = None,
        sort_field: Optional[Union[str, SortFieldPerson]] = None,
        sort_direction: Optional[Union[str, SortDirection]] = None,
    ) -> PeoplePaged:
        """GET /api/admin/companies/{companyId}/people"""
        params = {
            "page": page,
            "size": size,
            "statuses": statuses,
            "name": name,
            "email": email,
            "platforms": platforms,
            "uapMigrationStatuses": uap_migration_statuses,
            "credentialCount": credential_count,
            "creationDateFrom": creation_date_from,
            "creationDateTo": creation_date_to,
            "sortField": sort_field,
            "sortDirection": sort_direction,
        }
        data = self._get(f"/api/admin/companies/{company_id}/people", params)
        return PeoplePaged.model_validate(data)

    def get_credentials(
        self,
        company_id: CompanyId,
        *,
        page: int = 0,
        size: Optional[int] = None,
        statuses: Optional[Sequence[str]] = None,
        device_types: Optional[Sequence[str]] = None,
        name: Optional[str] = None,
        credential_number: Optional[str] = None,
        platforms: Optional[Sequence[Union[str, Platform]]] = None,
        uap_migration_statuses: Optional[Sequence[Union[str, UapMigrationStatus]]] = None,
        creation_date_from: Optional[Union[str, datetime]] = None,
        creation_date_to: Optional[Union[str, datetime]] = None,
        sort_field: Optional[Union[str, SortFieldCredential]] = None,
        sort_direction: Optional[Union[str, SortDirection]] = None,
    ) -> CredentialsPaged:
        """GET /api/admin/companies/{companyId}/credentials"""
        params = {
            "page": page,
            "size": size,
            "statuses": statuses,
            "deviceTypes": device_types,
            "name": name,
            "credentialNumber": credential_number,
            "platforms": platforms,
            "uapMigrationStatuses": uap_migration_statuses,
            "creationDateFrom": creation_date_from,
            "creationDateTo": creation_date_to,
            "sortField": sort_field,
            "sortDirection": sort_direction,
        }
        data = self._get(f"/api/admin/companies/{company_id}/credentials", params)
        return CredentialsPaged.model_validate(data)
