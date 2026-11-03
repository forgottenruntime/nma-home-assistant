"""Personal information on/off: config flow choice, fetching and entities."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nma.api import NmaSnapshot
from custom_components.nma.const import DOMAIN, OPT_PERSONAL_DATA
from custom_components.nma.nma_api.models import Company, Credential, Person

COMPANY_ID = "11111111-1111-1111-1111-111111111111"
PERSON_ID = "22222222-2222-2222-2222-222222222222"
TYPE = {"id": "33333333-3333-3333-3333-333333333333", "name": "Employee"}

COMPANY = Company.model_validate({
    "id": COMPANY_ID, "name": "Acme", "tenantId": "t1",
    "identityProvider": {"idpIssuer": "https://idp", "idpClientId": "c"},
    "status": "ACTIVE", "type": "SANDBOX",
    "limits": {"maxPeople": 10, "maxCredentials": 20}, "acs": "AEOS",
    "privacyOfficer": {"firstName": "Pat", "email": "pat@acme.test"},
    "enabledPlatforms": ["APPLE"],
    "acsWebSocket": {"up": True, "since": "2026-11-01T00:00:00Z"},
    "useAppKey": False, "uapMigrationStatus": "LEGACY",
})
PERSON = Person.model_validate({
    "id": PERSON_ID, "name": "Jane Doe", "email": "jane@acme.test",
    "status": "ACTIVE", "personType": TYPE, "credentialCount": 1,
    "platforms": ["APPLE"],
})
CREDENTIAL = Credential.model_validate({
    "id": "44444444-4444-4444-4444-444444444444", "number": 7,
    "deviceType": "PHONE", "status": "ACTIVE", "platform": "APPLE",
    "person": {"id": PERSON_ID, "name": "Jane Doe", "personType": TYPE},
})


class FakeApi:
    calls: list = []

    def __init__(self, base_url, token, company_id, **_):
        self.company_id = company_id
        self._client = type("C", (), {"base_url": base_url})()

    def fetch_company(self):
        return COMPANY

    def fetch_all(self, *, include_people, include_credentials):
        FakeApi.calls.append((include_people, include_credentials))
        return NmaSnapshot(
            company=COMPANY,
            people=[PERSON] if include_people else [],
            credentials=[CREDENTIAL] if include_credentials else [],
            people_total=1 if include_people else 0,
            credentials_total=1 if include_credentials else 0,
        )


def _entry(personal: bool) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={"base_url": "https://api.test", "token": "x",
              "company_id": COMPANY_ID, "verify_ssl": True},
        options={OPT_PERSONAL_DATA: personal},
    )


async def test_config_flow_defaults_to_health_only(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch("custom_components.nma.config_flow.NmaApi", FakeApi), patch(
        "custom_components.nma.NmaApi", FakeApi
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"base_url": "api.test/", "token": "x",
             "company_id": COMPANY_ID},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][OPT_PERSONAL_DATA] is False
    # No scheme typed: https:// is added.
    assert result["data"]["base_url"] == "https://api.test"


async def test_health_only_has_counts_but_no_personal_data(hass):
    entry = _entry(personal=False)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    # Left over from when personal data was on.
    stale = registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_person_{PERSON_ID}",
        config_entry=entry, suggested_object_id="nma_person_jane_doe",
    )
    FakeApi.calls.clear()
    with patch("custom_components.nma.NmaApi", FakeApi):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert FakeApi.calls == [(True, True)]
    assert registry.async_get(stale.entity_id) is None
    keys = {
        e.unique_id.removeprefix(f"{entry.entry_id}_")
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert {"acs_ws_up", "people_total", "people_type_employee",
            "credentials_type_employee", "people_credentials_1"} <= keys
    assert not [k for k in keys if k.startswith(("person_", "credential_"))]
    assert hass.states.get("sensor.acme_people_total").state == "1"
    assert hass.states.get("sensor.acme_credentials_on_phone").state == "1"
    for state in hass.states.async_all():
        text = str(state.attributes) + state.name
        assert "members" not in state.attributes, state.entity_id
        assert "Jane" not in text and "@" not in text, state.entity_id
    assert hass.states.get("binary_sensor.acme_acs_websocket").state == "on"
    assert hass.states.get("binary_sensor.acme_api_reachable").state == "on"


async def test_personal_data_on_keeps_everything(hass):
    entry = _entry(personal=True)
    entry.add_to_hass(hass)
    FakeApi.calls.clear()
    with patch("custom_components.nma.NmaApi", FakeApi):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert FakeApi.calls == [(True, True)]
    assert hass.states.get("sensor.acme_people_total").state == "1"
    assert "privacy_officer" in hass.states.get("sensor.acme_company_name").attributes
    registry = er.async_get(hass)
    assert registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_person_{PERSON_ID}"
    )
    # Empty buckets still expose the attribute, so templates always get a list.
    empty = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_people_status_blocked_by_acs"
    )
    assert hass.states.get(empty).state == "0"
    assert hass.states.get(empty).attributes["members"] == []


async def test_options_flow_opens_and_saves(hass):
    entry = _entry(personal=True)
    entry.add_to_hass(hass)
    with patch("custom_components.nma.NmaApi", FakeApi):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {OPT_PERSONAL_DATA: False}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[OPT_PERSONAL_DATA] is False
