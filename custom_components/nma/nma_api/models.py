"""Typed Pydantic models for the NMA API (mobile credentials).

These models map directly to the schemas defined in ``openapi.yaml``.
Attributes use snake_case in Python; the JSON wire format (camelCase) is
handled automatically via Pydantic's alias generator.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _Model(BaseModel):
    """Base model: read/write camelCase JSON, expose snake_case attributes."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class AppleDeviceTypes(str, Enum):
    IPHONE = "IPHONE"
    APPLE_WATCH = "APPLE_WATCH"


class CompanyACS(str, Enum):
    ATWORK = "ATWORK"
    AEOS = "AEOS"


class CompanyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING_FOR_DELETION = "PENDING_FOR_DELETION"
    DELETION_IN_PROGRESS = "DELETION_IN_PROGRESS"


class CompanyType(str, Enum):
    PRODUCTION = "PRODUCTION"
    SANDBOX = "SANDBOX"


class CompanyUapMigrationStatus(str, Enum):
    LEGACY = "LEGACY"
    MIGRATING = "MIGRATING"
    UAP = "UAP"


class CredentialStatus(str, Enum):
    PENDING_FOR_PLATFORM = "PENDING_FOR_PLATFORM"
    PENDING_FOR_ACS = "PENDING_FOR_ACS"
    ACTIVE = "ACTIVE"
    UNLINKED_BY_PLATFORM = "UNLINKED_BY_PLATFORM"
    BLOCKED_BY_PLATFORM = "BLOCKED_BY_PLATFORM"
    BLOCKED_BY_ACS = "BLOCKED_BY_ACS"
    PERSON_BLOCKED_BY_ACS = "PERSON_BLOCKED_BY_ACS"


class DeviceType(str, Enum):
    PHONE = "PHONE"
    WEARABLE = "WEARABLE"


class PersonStatus(str, Enum):
    ACTIVE = "ACTIVE"
    BLOCKED_BY_ACS = "BLOCKED_BY_ACS"
    INACTIVE = "INACTIVE"
    REMOVED_BY_ACS = "REMOVED_BY_ACS"


class Platform(str, Enum):
    APPLE = "APPLE"
    GOOGLE = "GOOGLE"
    UAP = "UAP"


class SortDirection(str, Enum):
    ASC = "ASC"
    DESC = "DESC"


class SortFieldCredential(str, Enum):
    CREDENTIAL_NUMBER = "CREDENTIAL_NUMBER"
    ACTIVATION_DATE = "ACTIVATION_DATE"
    PERSON = "PERSON"


class SortFieldPerson(str, Enum):
    NAME = "NAME"
    EMAIL = "EMAIL"
    CREATED_AT = "CREATED_AT"
    ACS_IDENTIFIER = "ACS_IDENTIFIER"
    STATUS = "STATUS"
    CREDENTIAL_COUNT = "CREDENTIAL_COUNT"


class UapMigrationStatus(str, Enum):
    LEGACY = "LEGACY"
    UAP = "UAP"
    MIGRATING = "MIGRATING"
    MIGRATION_FAILED = "MIGRATION_FAILED"


# --------------------------------------------------------------------------- #
# Object schemas
# --------------------------------------------------------------------------- #
class AcsWebSocket(_Model):
    up: bool
    since: datetime
    pending_messages_count: Optional[int] = None


class Address(_Model):
    street: Optional[str] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


class AppleDeviceTypeLimit(_Model):
    apple_device_type: AppleDeviceTypes
    max_number_of_devices: int = Field(ge=0, le=2)


class CompanyIdentityProvider(_Model):
    idp_issuer: str
    idp_email_claim: str = "email"
    idp_client_id: str


class CompanyLimits(_Model):
    max_people: int
    max_credentials: int


class Contact(_Model):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    email2: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[Address] = None


class PersonType(_Model):
    id: UUID
    name: str


class PersonDetails(_Model):
    id: UUID
    name: str
    person_type: PersonType


class Company(_Model):
    id: UUID
    name: str
    tenant_id: str
    address: Optional[Address] = None
    identity_provider: CompanyIdentityProvider
    tci_value: Optional[str] = None
    df_name: Optional[str] = None
    status: CompanyStatus
    type: CompanyType
    limits: CompanyLimits
    acs: CompanyACS
    bill_to: Optional[Contact] = None
    privacy_officer: Optional[Contact] = None
    sold_to: Optional[Contact] = None
    incident_contact: Optional[Contact] = None
    apple_device_type_limits: Optional[List[AppleDeviceTypeLimit]] = None
    enabled_platforms: List[Platform]
    acs_web_socket: AcsWebSocket
    use_app_key: bool
    uap_migration_status: CompanyUapMigrationStatus


class Credential(_Model):
    id: UUID
    number: int
    device_type: DeviceType
    creation_date: Optional[datetime] = None
    person: PersonDetails
    status: CredentialStatus
    platform: Platform
    uap_migration_status: Optional[UapMigrationStatus] = None


class Person(_Model):
    id: UUID
    name: str
    email: str
    status: PersonStatus
    person_type: PersonType
    creation_date: Optional[datetime] = None
    credential_count: int
    platforms: List[Platform]
    uap_migration_status: Optional[UapMigrationStatus] = None


class PageInfo(_Model):
    page: int
    size: int
    total_pages: int
    total_elements: int


class CredentialsPaged(_Model):
    items: List[Credential] = Field(default_factory=list)
    page_info: PageInfo


class PeoplePaged(_Model):
    items: List[Person] = Field(default_factory=list)
    page_info: PageInfo


class Error(_Model):
    code: int
    message: str
    resource_key: Optional[str] = None
