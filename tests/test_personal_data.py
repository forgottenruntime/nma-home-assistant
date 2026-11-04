"""Personal information on/off: config flow choice, fetching and entities."""
import threading
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nma.api import NmaLists
from custom_components.nma.const import DOMAIN, OPT_PAGE_SIZE, OPT_PERSONAL_DATA
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
    release = None  # threading.Event: hold fetch_lists until set

    def __init__(self, base_url, token, company_id, **_):
        self.company_id = company_id
        self._client = type("C", (), {"base_url": base_url})()

    def fetch_company(self):
        return COMPANY

    def fetch_lists(self, *, include_people, include_credentials):
        if FakeApi.release is not None:
            FakeApi.release.wait(5)
        FakeApi.calls.append((include_people, include_credentials))
        return NmaLists(
            people=[PERSON] if include_people else [],
            people_total=1 if include_people else 0,
            credentials=[CREDENTIAL] if include_credentials else [],
            credentials_total=1 if include_credentials else 0,
            requests=2,
        )

    def close(self):
        pass


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
        await hass.async_block_till_done(wait_background_tasks=True)
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
        await hass.async_block_till_done(wait_background_tasks=True)

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
        await hass.async_block_till_done(wait_background_tasks=True)

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
        await hass.async_block_till_done(wait_background_tasks=True)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {OPT_PERSONAL_DATA: False}
        )
        await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[OPT_PERSONAL_DATA] is False


async def test_setup_does_not_wait_for_people_sync(hass):
    """A big company pages for minutes; setup must not wait for it."""
    entry = _entry(personal=False)
    entry.add_to_hass(hass)
    FakeApi.calls.clear()
    FakeApi.release = threading.Event()
    try:
        with patch("custom_components.nma.NmaApi", FakeApi):
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
            # Health is there, counts are unknown until the sync finishes.
            assert hass.states.get("binary_sensor.acme_api_reachable").state == "on"
            assert hass.states.get("sensor.acme_people_total").state == "unknown"
            assert hass.states.get("sensor.acme_people_active").state == "unknown"
            FakeApi.release.set()
            await hass.async_block_till_done(wait_background_tasks=True)
    finally:
        FakeApi.release = None
    assert hass.states.get("sensor.acme_people_total").state == "1"
    assert hass.states.get("sensor.acme_people_active").state == "1"


async def test_migration_raises_old_page_size_to_100(hass):
    entry = _entry(personal=False)
    entry = MockConfigEntry(
        domain=DOMAIN, data=entry.data, minor_version=1,
        options={OPT_PERSONAL_DATA: False, OPT_PAGE_SIZE: 50},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.nma.NmaApi", FakeApi):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.minor_version == 2
    assert entry.options[OPT_PAGE_SIZE] == 100


def test_api_pages_at_100_and_stops_on_close():
    from types import SimpleNamespace

    import pytest

    from custom_components.nma.api import NmaApi, NmaApiError

    def pages(total):
        def get(company_id, page, size):
            n = max(0, min(size, total - page * size))
            return SimpleNamespace(
                items=[PERSON] * n,
                page_info=SimpleNamespace(
                    total_elements=total, total_pages=-(-total // size)
                ),
            )
        return get

    api = NmaApi("https://api.test", "x", COMPANY_ID, page_size=100)
    api._client.get_people = pages(250)
    api._client.get_credentials = pages(150)
    lists = api.fetch_lists()
    assert (lists.people_total, len(lists.people)) == (250, 250)
    assert (lists.credentials_total, len(lists.credentials)) == (150, 150)
    assert lists.requests == 3 + 2

    api.close()
    with pytest.raises(NmaApiError):
        api.fetch_lists()


async def test_api_unreachable_shows_short_error_and_code(hass):
    import requests

    from custom_components.nma.api import NmaApiError

    entry = _entry(personal=False)
    entry.add_to_hass(hass)
    with patch("custom_components.nma.NmaApi", FakeApi):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        coordinator = hass.data[DOMAIN][entry.entry_id]

        for err, code, text in [
            (NmaApiError(502, message="Bad Gateway"), 502, "[502] Bad Gateway"),
            (requests.ConnectTimeout("HTTPSConnectionPool(host='x', port=443): Max retries"),
             "timeout", "No answer from the API in time (timeout)"),
            (requests.ConnectionError("HTTPSConnectionPool(...) NameResolutionError(...)"),
             "dns", "Host name not found (DNS)"),
        ]:
            with patch.object(FakeApi, "fetch_company", side_effect=err):
                await coordinator.async_refresh()
                await hass.async_block_till_done()
            st = hass.states.get("binary_sensor.acme_api_reachable")
            assert st.state == "off"
            assert st.attributes["last_error"] == text
            assert st.attributes["last_error_code"] == code

        await coordinator.async_refresh()  # API answers again
        st = hass.states.get("binary_sensor.acme_api_reachable")
        assert st.state == "on" and "last_error_code" not in st.attributes


def test_429_pauses_every_connection():
    import threading
    import time as _time

    import pytest

    from custom_components.nma import api as nma_api

    a = nma_api.NmaApi("https://a.test", "x", COMPANY_ID)
    b = nma_api.NmaApi("https://b.test", "x", COMPANY_ID)

    def too_many(*_, **__):
        raise nma_api.NmaApiError(429, message="Too Many Requests")

    a._client.get_company = too_many
    try:
        with pytest.raises(nma_api.NmaApiError):
            a.fetch_company()
        # Connection b shares the limiter, so it is paused too.
        assert nma_api._LIMITER._paused_until > _time.monotonic() + 50
    finally:
        nma_api._LIMITER._paused_until = 0.0

    # A paused limiter holds callers; stop() lets them go at once.
    limiter = nma_api._RateLimiter(5, 60.0)
    limiter.pause(0.2)
    t0 = _time.monotonic()
    limiter.acquire(threading.Event())
    assert _time.monotonic() - t0 >= 0.19
    limiter.pause(30)
    stop = threading.Event()
    stop.set()
    t0 = _time.monotonic()
    limiter.acquire(stop)
    assert _time.monotonic() - t0 < 1
    assert b is not a
