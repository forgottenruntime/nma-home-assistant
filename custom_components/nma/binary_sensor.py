"""Binary sensor entities for NMA Mobile Credentials.

Two binary sensors:

* ``binary_sensor.<company>_acs_websocket`` — ACS↔backend WebSocket up/down,
  reflects ``Company.acs_web_socket.up``.
* ``binary_sensor.<company>_api_reachable`` — true while the most recent
  coordinator poll succeeded (connection-alive watchdog).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import NmaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NmaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AcsWebSocketUpBinarySensor(coordinator),
            ApiReachableBinarySensor(coordinator),
        ]
    )


def _device_info(coordinator: NmaCoordinator) -> DeviceInfo:
    company = coordinator.data.company if coordinator.data else None
    return DeviceInfo(
        identifiers={(DOMAIN, str(coordinator.api.company_id))},
        name=company.name if company else f"NMA {coordinator.api.company_id}",
        manufacturer=MANUFACTURER,
        model=MODEL,
        configuration_url=coordinator.api._client.base_url,  # noqa: SLF001
    )


class AcsWebSocketUpBinarySensor(
    CoordinatorEntity[NmaCoordinator], BinarySensorEntity
):
    """True when ``Company.acsWebSocket.up`` is true."""

    _attr_has_entity_name = True
    _attr_name = "ACS WebSocket"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:lan-connect"

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_acs_ws_up"
        self._attr_device_info = _device_info(coordinator)

    @property
    def is_on(self) -> Optional[bool]:
        c = self.coordinator.data.company if self.coordinator.data else None
        return c.acs_web_socket.up if c else None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        c = self.coordinator.data.company if self.coordinator.data else None
        if not c:
            return {}
        ws = c.acs_web_socket
        return {
            "since": ws.since.isoformat() if ws.since else None,
            "pending_messages_count": ws.pending_messages_count,
        }


class ApiReachableBinarySensor(
    CoordinatorEntity[NmaCoordinator], BinarySensorEntity
):
    """True while the latest coordinator poll succeeded."""

    _attr_has_entity_name = True
    _attr_name = "API reachable"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:cloud-check"

    def __init__(self, coordinator: NmaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_api_reachable"
        self._attr_device_info = _device_info(coordinator)

    # Always available — that's the whole point of this sensor.
    @property
    def available(self) -> bool:  # noqa: D401
        return True

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.last_update_success)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        d = self.coordinator.data
        attrs: Dict[str, Any] = {
            "base_url": self.coordinator.api._client.base_url,  # noqa: SLF001
            "company_id": str(self.coordinator.api.company_id),
        }
        if d:
            attrs["last_fetched_at"] = d.fetched_at.isoformat()
            attrs["last_fetch_duration_s"] = round(d.duration_s, 3)
            attrs["people_total"] = d.people_total
            attrs["credentials_total"] = d.credentials_total
        if self.coordinator.last_exception:
            attrs["last_error"] = str(self.coordinator.last_exception)
        # `next_update_at` for visibility
        if self.coordinator.update_interval and isinstance(
            d.fetched_at if d else None, datetime
        ):
            attrs["polling_interval_s"] = int(
                self.coordinator.update_interval.total_seconds()
            )
        return attrs
