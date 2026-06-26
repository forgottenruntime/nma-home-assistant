"""Sensor entities for NMA Mobile Credentials.

This module exposes a *lot* of entities — most are static one-per-company,
plus optional one-entity-per-person and one-entity-per-credential dynamic
sets (disabled by default).
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Optional, Set

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import NmaCoordinator
from .nma_api.models import (
    CompanyACS,
    CompanyStatus,
    CompanyType,
    CompanyUapMigrationStatus,
    Credential,
    CredentialStatus,
    DeviceType,
    Person,
    PersonStatus,
    Platform,
    UapMigrationStatus,
)

_LOGGER = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Setup entry
# --------------------------------------------------------------------------- #
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NMA sensors from a config entry."""
    coordinator: NmaCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: List[SensorEntity] = [
        CompanyNameSensor(coordinator),
        CompanyTenantSensor(coordinator),
        CompanyStatusSensor(coordinator),
        CompanyTypeSensor(coordinator),
        CompanyAcsSensor(coordinator),
        CompanyUapMigrationSensor(coordinator),
        CompanyMaxPeopleSensor(coordinator),
        CompanyMaxCredentialsSensor(coordinator),
        CompanyEnabledPlatformsSensor(coordinator),
        CompanyUseAppKeySensor(coordinator),
        CompanyDfNameSensor(coordinator),
        CompanyTciValueSensor(coordinator),
        AcsWsPendingMessagesSensor(coordinator),
        AcsWsSinceSensor(coordinator),
        TotalPeopleSensor(coordinator),
        TotalCredentialsSensor(coordinator),
        LastUpdateSensor(coordinator),
        LastUpdateDurationSensor(coordinator),
        AcsWsOutagesSensor(coordinator),
        AcsWsOfflineSinceSensor(coordinator),
        ApiOutagesSensor(coordinator),
    ]

    for status in PersonStatus:
        entities.append(_people_by_status(coordinator, status))
    for platform in Platform:
        entities.append(_people_by_platform(coordinator, platform))
    for ums in UapMigrationStatus:
        entities.append(_people_by_uap(coordinator, ums))

    for cstatus in CredentialStatus:
        entities.append(_credentials_by_status(coordinator, cstatus))
    for platform in Platform:
        entities.append(_credentials_by_platform(coordinator, platform))
    for dt in DeviceType:
        entities.append(_credentials_by_device(coordinator, dt))
    for ums in UapMigrationStatus:
        entities.append(_credentials_by_uap(coordinator, ums))

    # People bucketed by how many credentials (devices) they hold.
    entities.append(
        _people_by_credential_count(
            coordinator,
            "people_credentials_0",
            "People with 0 credentials",
            lambda p: p.credential_count == 0,
            icon="mdi:account-cancel",
        )
    )
    entities.append(
        _people_by_credential_count(
            coordinator,
            "people_credentials_1",
            "People with 1 credential",
            lambda p: p.credential_count == 1,
            icon="mdi:account",
        )
    )
    entities.append(
        _people_by_credential_count(
            coordinator,
            "people_credentials_2",
            "People with 2 credentials",
            lambda p: p.credential_count == 2,
            icon="mdi:account-multiple",
        )
    )
    entities.append(
        _people_by_credential_count(
            coordinator,
            "people_credentials_3plus",
            "People with 3+ credentials",
            lambda p: p.credential_count >= 3,
            icon="mdi:account-group",
        )
    )

    async_add_entities(entities)

    # People / credentials counted per (company-defined) person type, e.g.
    # Employee / Contractor / Visitor. Discovered dynamically from the data.
    _DynamicPersonTypeAdder(coordinator, async_add_entities).start()

    # Dynamic per-person / per-credential entities (disabled by default).
    _DynamicPersonAdder(coordinator, async_add_entities).start()
    _DynamicCredentialAdder(coordinator, async_add_entities).start()


# --------------------------------------------------------------------------- #
# Device + base
# --------------------------------------------------------------------------- #
def _company_device_info(coordinator: NmaCoordinator) -> DeviceInfo:
    company = coordinator.data.company if coordinator.data else None
    return DeviceInfo(
        identifiers={(DOMAIN, str(coordinator.api.company_id))},
        name=company.name if company else f"NMA {coordinator.api.company_id}",
        manufacturer=MANUFACTURER,
        model=MODEL,
        configuration_url=coordinator.api._client.base_url,  # noqa: SLF001
    )


class _NmaBaseSensor(CoordinatorEntity[NmaCoordinator], SensorEntity):
    """Common base — company-scoped entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NmaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = _company_device_info(coordinator)


# --------------------------------------------------------------------------- #
# Company-level sensors
# --------------------------------------------------------------------------- #
class CompanyNameSensor(_NmaBaseSensor):
    _attr_name = "Company name"
    _attr_icon = "mdi:office-building"

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "company_name")

    @property
    def native_value(self) -> Optional[str]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return c.name if c else None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        c = self.coordinator.data.company if self.coordinator.data else None
        if not c:
            return {}
        attrs: Dict[str, Any] = {"id": str(c.id)}
        if c.address:
            attrs["address"] = c.address.model_dump(by_alias=True, exclude_none=True)
        if c.bill_to:
            attrs["bill_to"] = c.bill_to.model_dump(by_alias=True, exclude_none=True)
        if c.privacy_officer:
            attrs["privacy_officer"] = c.privacy_officer.model_dump(
                by_alias=True, exclude_none=True
            )
        if c.incident_contact:
            attrs["incident_contact"] = c.incident_contact.model_dump(
                by_alias=True, exclude_none=True
            )
        if c.sold_to:
            attrs["sold_to"] = c.sold_to.model_dump(by_alias=True, exclude_none=True)
        if c.apple_device_type_limits:
            attrs["apple_device_type_limits"] = [
                limit.model_dump(by_alias=True) for limit in c.apple_device_type_limits
            ]
        attrs["identity_provider"] = c.identity_provider.model_dump(
            by_alias=True, exclude_none=True
        )
        return attrs


class CompanyTenantSensor(_NmaBaseSensor):
    _attr_name = "Tenant ID"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:identifier"

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "tenant_id")

    @property
    def native_value(self) -> Optional[str]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return c.tenant_id if c else None


class CompanyStatusSensor(_NmaBaseSensor):
    _attr_name = "Company status"
    _attr_icon = "mdi:check-decagram"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [s.value for s in CompanyStatus]

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "company_status")

    @property
    def native_value(self) -> Optional[str]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return c.status.value if c else None


class CompanyTypeSensor(_NmaBaseSensor):
    _attr_name = "Company type"
    _attr_icon = "mdi:tag"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [s.value for s in CompanyType]

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "company_type")

    @property
    def native_value(self) -> Optional[str]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return c.type.value if c else None


class CompanyAcsSensor(_NmaBaseSensor):
    _attr_name = "ACS"
    _attr_icon = "mdi:server-network"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [s.value for s in CompanyACS]

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "acs")

    @property
    def native_value(self) -> Optional[str]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return c.acs.value if c else None


class CompanyUapMigrationSensor(_NmaBaseSensor):
    _attr_name = "UAP migration status"
    _attr_icon = "mdi:swap-horizontal"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [s.value for s in CompanyUapMigrationStatus]

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "uap_migration_status")

    @property
    def native_value(self) -> Optional[str]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return c.uap_migration_status.value if c else None


class CompanyMaxPeopleSensor(_NmaBaseSensor):
    _attr_name = "Max people"
    _attr_icon = "mdi:account-multiple-outline"
    _attr_native_unit_of_measurement = "people"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "max_people")

    @property
    def native_value(self) -> Optional[int]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return c.limits.max_people if c else None


class CompanyMaxCredentialsSensor(_NmaBaseSensor):
    _attr_name = "Max credentials"
    _attr_icon = "mdi:cellphone-key"
    _attr_native_unit_of_measurement = "credentials"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "max_credentials")

    @property
    def native_value(self) -> Optional[int]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return c.limits.max_credentials if c else None


class CompanyEnabledPlatformsSensor(_NmaBaseSensor):
    _attr_name = "Enabled platforms"
    _attr_icon = "mdi:cellphone-link"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "enabled_platforms")

    @property
    def native_value(self) -> Optional[int]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return len(c.enabled_platforms) if c else None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        c = self.coordinator.data.company if self.coordinator.data else None
        if not c:
            return {}
        return {"platforms": [p.value for p in c.enabled_platforms]}


class CompanyUseAppKeySensor(_NmaBaseSensor):
    _attr_name = "Use app key"
    _attr_icon = "mdi:key"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "use_app_key")

    @property
    def native_value(self) -> Optional[str]:
        c = self.coordinator.data.company if self.coordinator.data else None
        if not c:
            return None
        return "true" if c.use_app_key else "false"


class CompanyDfNameSensor(_NmaBaseSensor):
    _attr_name = "DF name"
    _attr_icon = "mdi:file-document"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "df_name")

    @property
    def native_value(self) -> Optional[str]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return c.df_name if c else None


class CompanyTciValueSensor(_NmaBaseSensor):
    _attr_name = "TCI value"
    _attr_icon = "mdi:numeric"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "tci_value")

    @property
    def native_value(self) -> Optional[str]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return c.tci_value if c else None


# --------------------------------------------------------------------------- #
# ACS WebSocket
# --------------------------------------------------------------------------- #
class AcsWsPendingMessagesSensor(_NmaBaseSensor):
    _attr_name = "ACS WebSocket pending messages"
    _attr_icon = "mdi:message-processing"
    _attr_native_unit_of_measurement = "messages"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "acs_ws_pending")

    @property
    def native_value(self) -> Optional[int]:
        c = self.coordinator.data.company if self.coordinator.data else None
        if not c:
            return None
        return c.acs_web_socket.pending_messages_count


class AcsWsSinceSensor(_NmaBaseSensor):
    _attr_name = "ACS WebSocket up since"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check"

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "acs_ws_since")

    @property
    def native_value(self) -> Optional[datetime]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return c.acs_web_socket.since if c else None


# --------------------------------------------------------------------------- #
# People / credentials totals
# --------------------------------------------------------------------------- #
class TotalPeopleSensor(_NmaBaseSensor):
    _attr_name = "People total"
    _attr_icon = "mdi:account-multiple"
    _attr_native_unit_of_measurement = "people"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "people_total")

    @property
    def native_value(self) -> Optional[int]:
        d = self.coordinator.data
        return d.people_total if d else None


class TotalCredentialsSensor(_NmaBaseSensor):
    _attr_name = "Credentials total"
    _attr_icon = "mdi:cellphone-key"
    _attr_native_unit_of_measurement = "credentials"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "credentials_total")

    @property
    def native_value(self) -> Optional[int]:
        d = self.coordinator.data
        return d.credentials_total if d else None


# --------------------------------------------------------------------------- #
# Breakdown count sensors (one factory per dimension)
# --------------------------------------------------------------------------- #
# Cap how many member names we expose as an attribute, to keep the attribute
# (and the recorder row) from growing unbounded on large buckets.
_MAX_MEMBERS = 50

# Friendly device labels derived from (platform, device_type). The API only
# distinguishes PHONE vs WEARABLE and the platform; these labels are a
# best-effort human-readable interpretation (e.g. an Apple wearable is an
# Apple Watch). Unknown combinations fall back to "<Platform> <DeviceType>".
_DEVICE_LABELS = {
    (Platform.APPLE, DeviceType.PHONE): "iPhone",
    (Platform.APPLE, DeviceType.WEARABLE): "Apple Watch",
    (Platform.GOOGLE, DeviceType.PHONE): "Android phone",
    (Platform.GOOGLE, DeviceType.WEARABLE): "Wear OS watch",
    (Platform.UAP, DeviceType.PHONE): "Phone (UAP)",
    (Platform.UAP, DeviceType.WEARABLE): "Wearable (UAP)",
}


def _device_label(platform: Platform, device_type: DeviceType) -> str:
    return _DEVICE_LABELS.get(
        (platform, device_type), f"{platform.value} {device_type.value}"
    )


class _CountSensor(_NmaBaseSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: NmaCoordinator,
        key: str,
        name: str,
        unit: str,
        predicate: Callable[[Any], bool],
        source: str,
        icon: str = "mdi:counter",
    ) -> None:
        super().__init__(coordinator, key)
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._predicate = predicate
        self._source = source  # "people" or "credentials"

    def _matches(self) -> list:
        d = self.coordinator.data
        if not d:
            return []
        items = d.people if self._source == "people" else d.credentials
        return [item for item in items if self._predicate(item)]

    @property
    def native_value(self) -> Optional[int]:
        if self.coordinator.data is None:
            return None
        return len(self._matches())

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        matches = self._matches()
        if not matches:
            return {}
        if self._source == "people":
            # Map person id -> their device labels (joined from credentials).
            by_person: Dict[str, list] = {}
            data = self.coordinator.data
            if data:
                for cred in data.credentials:
                    by_person.setdefault(str(cred.person.id), []).append(
                        _device_label(cred.platform, cred.device_type)
                    )
            members = [
                {
                    "name": p.name,
                    "email": p.email,
                    "id": str(p.id),
                    "devices": by_person.get(str(p.id), []),
                }
                for p in matches[:_MAX_MEMBERS]
            ]
        else:
            members = [
                {
                    "number": c.number,
                    "person": c.person.name,
                    "id": str(c.id),
                    "device_type": c.device_type.value,
                    "platform": c.platform.value,
                    "device": _device_label(c.platform, c.device_type),
                }
                for c in matches[:_MAX_MEMBERS]
            ]
        attrs: Dict[str, Any] = {"members": members}
        if len(matches) > _MAX_MEMBERS:
            attrs["members_truncated"] = len(matches) - _MAX_MEMBERS
        return attrs


def _people_by_status(
    coordinator: NmaCoordinator, status: PersonStatus
) -> _CountSensor:
    return _CountSensor(
        coordinator,
        key=f"people_status_{status.value.lower()}",
        name=f"People {status.value.replace('_', ' ').title()}",
        unit="people",
        predicate=lambda p: p.status == status,
        source="people",
        icon="mdi:account-check" if status == PersonStatus.ACTIVE else "mdi:account-off",
    )


def _people_by_platform(
    coordinator: NmaCoordinator, platform: Platform
) -> _CountSensor:
    return _CountSensor(
        coordinator,
        key=f"people_platform_{platform.value.lower()}",
        name=f"People on {platform.value.title()}",
        unit="people",
        predicate=lambda p: platform in p.platforms,
        source="people",
        icon="mdi:account-group",
    )


def _people_by_uap(
    coordinator: NmaCoordinator, status: UapMigrationStatus
) -> _CountSensor:
    return _CountSensor(
        coordinator,
        key=f"people_uap_{status.value.lower()}",
        name=f"People UAP {status.value.replace('_', ' ').title()}",
        unit="people",
        predicate=lambda p: p.uap_migration_status == status,
        source="people",
        icon="mdi:account-convert",
    )


def _people_by_credential_count(
    coordinator: NmaCoordinator,
    key: str,
    name: str,
    predicate: Callable[[Any], bool],
    *,
    icon: str = "mdi:account-multiple",
) -> _CountSensor:
    return _CountSensor(
        coordinator,
        key=key,
        name=name,
        unit="people",
        predicate=predicate,
        source="people",
        icon=icon,
    )


def _people_by_person_type(
    coordinator: NmaCoordinator, slug: str, type_name: str
) -> _CountSensor:
    return _CountSensor(
        coordinator,
        key=f"people_type_{slug}",
        name=f"People {type_name}",
        unit="people",
        predicate=lambda p: p.person_type.name == type_name,
        source="people",
        icon="mdi:account-tie",
    )


def _credentials_by_person_type(
    coordinator: NmaCoordinator, slug: str, type_name: str
) -> _CountSensor:
    return _CountSensor(
        coordinator,
        key=f"credentials_type_{slug}",
        name=f"Credentials {type_name}",
        unit="credentials",
        predicate=lambda c: c.person.person_type.name == type_name,
        source="credentials",
        icon="mdi:card-account-details",
    )


def _credentials_by_status(
    coordinator: NmaCoordinator, status: CredentialStatus
) -> _CountSensor:
    return _CountSensor(
        coordinator,
        key=f"credentials_status_{status.value.lower()}",
        name=f"Credentials {status.value.replace('_', ' ').title()}",
        unit="credentials",
        predicate=lambda c: c.status == status,
        source="credentials",
        icon="mdi:cellphone-key",
    )


def _credentials_by_platform(
    coordinator: NmaCoordinator, platform: Platform
) -> _CountSensor:
    return _CountSensor(
        coordinator,
        key=f"credentials_platform_{platform.value.lower()}",
        name=f"Credentials on {platform.value.title()}",
        unit="credentials",
        predicate=lambda c: c.platform == platform,
        source="credentials",
        icon="mdi:cellphone-link",
    )


def _credentials_by_device(
    coordinator: NmaCoordinator, dt: DeviceType
) -> _CountSensor:
    return _CountSensor(
        coordinator,
        key=f"credentials_device_{dt.value.lower()}",
        name=f"Credentials on {dt.value.title()}",
        unit="credentials",
        predicate=lambda c: c.device_type == dt,
        source="credentials",
        icon="mdi:watch" if dt == DeviceType.WEARABLE else "mdi:cellphone",
    )


def _credentials_by_uap(
    coordinator: NmaCoordinator, status: UapMigrationStatus
) -> _CountSensor:
    return _CountSensor(
        coordinator,
        key=f"credentials_uap_{status.value.lower()}",
        name=f"Credentials UAP {status.value.replace('_', ' ').title()}",
        unit="credentials",
        predicate=lambda c: c.uap_migration_status == status,
        source="credentials",
        icon="mdi:swap-horizontal-bold",
    )


# --------------------------------------------------------------------------- #
# Coordinator health
# --------------------------------------------------------------------------- #
class LastUpdateSensor(_NmaBaseSensor):
    _attr_name = "Last successful update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:cloud-sync"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "last_update")

    @property
    def native_value(self) -> Optional[datetime]:
        d = self.coordinator.data
        return d.fetched_at if d else None


class LastUpdateDurationSensor(_NmaBaseSensor):
    _attr_name = "Last update duration"
    _attr_native_unit_of_measurement = "s"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator, "last_update_duration")

    @property
    def native_value(self) -> Optional[float]:
        d = self.coordinator.data
        return round(d.duration_s, 3) if d else None


# --------------------------------------------------------------------------- #
# Connectivity outage tracking (derived by observing transitions across polls)
# --------------------------------------------------------------------------- #
class _OutageCounterSensor(CoordinatorEntity[NmaCoordinator], RestoreSensor):
    """Counts how many times a connectivity signal went up -> down.

    Restored across restarts (``RestoreSensor``) and exposed as a
    ``total_increasing`` measurement, so Home Assistant long-term statistics can
    derive outages-per-day / per-week. Answers the client's
    "how many times offline over time".
    """

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "outages"

    def __init__(
        self, coordinator: NmaCoordinator, key: str, name: str, icon: str
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_info = _company_device_info(coordinator)
        self._count = 0
        self._prev_up: Optional[bool] = None

    def _is_up(self) -> Optional[bool]:
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            try:
                self._count = int(last.native_value)
            except (TypeError, ValueError):
                self._count = 0
        # Baseline so a signal that is already down at startup is not counted.
        self._prev_up = self._is_up()

    @callback
    def _handle_coordinator_update(self) -> None:
        up = self._is_up()
        if up is False and self._prev_up is True:
            self._count += 1
        if up is not None:
            self._prev_up = up
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> int:
        return self._count


class AcsWsOutagesSensor(_OutageCounterSensor):
    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(
            coordinator,
            "acs_ws_outages",
            "ACS WebSocket outages",
            "mdi:lan-disconnect",
        )

    def _is_up(self) -> Optional[bool]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return c.acs_web_socket.up if c else None


class ApiOutagesSensor(_OutageCounterSensor):
    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(
            coordinator,
            "api_outages",
            "API outages",
            "mdi:cloud-alert",
        )

    def _is_up(self) -> Optional[bool]:
        return bool(self.coordinator.last_update_success)


class AcsWsOfflineSinceSensor(CoordinatorEntity[NmaCoordinator], SensorEntity):
    """Timestamp the ACS WebSocket was first observed down (``None`` when up).

    Lets the UI show a live "offline for N minutes" — answering the client's
    "how long offline since it is up". Resets if HA restarts while offline.
    """

    _attr_has_entity_name = True
    _attr_name = "ACS WebSocket offline since"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-alert"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_acs_ws_offline_since"
        self._attr_device_info = _company_device_info(coordinator)
        self._offline_since: Optional[datetime] = None

    def _is_up(self) -> Optional[bool]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return c.acs_web_socket.up if c else None

    @callback
    def _handle_coordinator_update(self) -> None:
        up = self._is_up()
        if up is True:
            self._offline_since = None
        elif up is False and self._offline_since is None:
            self._offline_since = datetime.now(timezone.utc)
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> Optional[datetime]:
        return self._offline_since


# --------------------------------------------------------------------------- #
# Per-Person + Per-Credential dynamic entities (disabled by default)
# --------------------------------------------------------------------------- #
class PersonSensor(CoordinatorEntity[NmaCoordinator], SensorEntity):
    _attr_has_entity_name = False
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:account"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [s.value for s in PersonStatus]

    def __init__(self, coordinator: NmaCoordinator, person: Person) -> None:
        super().__init__(coordinator)
        self._person_id = str(person.id)
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_person_{self._person_id}"
        )
        self._attr_name = f"NMA Person {person.name}"
        self._attr_device_info = _company_device_info(coordinator)

    def _person(self) -> Optional[Person]:
        d = self.coordinator.data
        if not d:
            return None
        for p in d.people:
            if str(p.id) == self._person_id:
                return p
        return None

    @property
    def available(self) -> bool:
        return super().available and self._person() is not None

    @property
    def native_value(self) -> Optional[str]:
        p = self._person()
        return p.status.value if p else None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        p = self._person()
        if not p:
            return {}
        data = self.coordinator.data
        devices = []
        if data:
            devices = [
                _device_label(c.platform, c.device_type)
                for c in data.credentials
                if str(c.person.id) == self._person_id
            ]
        return {
            "id": str(p.id),
            "name": p.name,
            "email": p.email,
            "credential_count": p.credential_count,
            "person_type": p.person_type.name,
            "person_type_id": str(p.person_type.id),
            "creation_date": (
                p.creation_date.isoformat() if p.creation_date else None
            ),
            "platforms": [pl.value for pl in p.platforms],
            "devices": devices,
            "uap_migration_status": (
                p.uap_migration_status.value if p.uap_migration_status else None
            ),
        }


class CredentialSensor(CoordinatorEntity[NmaCoordinator], SensorEntity):
    _attr_has_entity_name = False
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:cellphone-key"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [s.value for s in CredentialStatus]

    def __init__(
        self, coordinator: NmaCoordinator, credential: Credential
    ) -> None:
        super().__init__(coordinator)
        self._credential_id = str(credential.id)
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_credential_{self._credential_id}"
        )
        self._attr_name = (
            f"NMA Credential #{credential.number} ({credential.person.name})"
        )
        self._attr_device_info = _company_device_info(coordinator)

    def _credential(self) -> Optional[Credential]:
        d = self.coordinator.data
        if not d:
            return None
        for c in d.credentials:
            if str(c.id) == self._credential_id:
                return c
        return None

    @property
    def available(self) -> bool:
        return super().available and self._credential() is not None

    @property
    def native_value(self) -> Optional[str]:
        c = self._credential()
        return c.status.value if c else None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        c = self._credential()
        if not c:
            return {}
        return {
            "id": str(c.id),
            "number": c.number,
            "device_type": c.device_type.value,
            "platform": c.platform.value,
            "person_id": str(c.person.id),
            "person_name": c.person.name,
            "person_type": c.person.person_type.name,
            "creation_date": (
                c.creation_date.isoformat() if c.creation_date else None
            ),
            "uap_migration_status": (
                c.uap_migration_status.value if c.uap_migration_status else None
            ),
        }


# --------------------------------------------------------------------------- #
# Dynamic adders
# --------------------------------------------------------------------------- #
class _DynamicAdderBase:
    """Listens to coordinator updates and adds new entities for new items."""

    def __init__(
        self,
        coordinator: NmaCoordinator,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self._coordinator = coordinator
        self._async_add_entities = async_add_entities
        self._seen: Set[str] = set()

    def start(self) -> None:
        self._coordinator.async_add_listener(self._on_update)
        # Run once now if we already have data
        if self._coordinator.data is not None:
            self._on_update()

    @callback
    def _on_update(self) -> None:
        raise NotImplementedError


class _DynamicPersonAdder(_DynamicAdderBase):
    @callback
    def _on_update(self) -> None:
        data = self._coordinator.data
        if data is None:
            return
        new: List[SensorEntity] = []
        for person in data.people:
            pid = str(person.id)
            if pid in self._seen:
                continue
            self._seen.add(pid)
            new.append(PersonSensor(self._coordinator, person))
        if new:
            _LOGGER.debug("Adding %d new PersonSensor entities", len(new))
            self._async_add_entities(new)


class _DynamicCredentialAdder(_DynamicAdderBase):
    @callback
    def _on_update(self) -> None:
        data = self._coordinator.data
        if data is None:
            return
        new: List[SensorEntity] = []
        for credential in data.credentials:
            cid = str(credential.id)
            if cid in self._seen:
                continue
            self._seen.add(cid)
            new.append(CredentialSensor(self._coordinator, credential))
        if new:
            _LOGGER.debug("Adding %d new CredentialSensor entities", len(new))
            self._async_add_entities(new)


class _DynamicPersonTypeAdder(_DynamicAdderBase):
    """Creates People- and Credentials-by-type count sensors per discovered
    person type (company-defined, e.g. Employee / Contractor / Visitor)."""

    @callback
    def _on_update(self) -> None:
        data = self._coordinator.data
        if data is None:
            return
        # slug -> display name, gathered from both people and credentials.
        types: Dict[str, str] = {}
        for p in data.people:
            types.setdefault(slugify(p.person_type.name), p.person_type.name)
        for c in data.credentials:
            types.setdefault(
                slugify(c.person.person_type.name), c.person.person_type.name
            )

        new: List[SensorEntity] = []
        for slug, name in types.items():
            people_key = f"people_type_{slug}"
            if people_key not in self._seen:
                self._seen.add(people_key)
                new.append(_people_by_person_type(self._coordinator, slug, name))
            cred_key = f"credentials_type_{slug}"
            if cred_key not in self._seen:
                self._seen.add(cred_key)
                new.append(
                    _credentials_by_person_type(self._coordinator, slug, name)
                )
        if new:
            _LOGGER.debug("Adding %d new person-type count sensors", len(new))
            self._async_add_entities(new)
