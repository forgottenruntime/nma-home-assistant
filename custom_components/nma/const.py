"""Constants for the NMA Mobile Credentials integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "nma"

CONF_BASE_URL = "base_url"
CONF_TOKEN = "token"
CONF_COMPANY_ID = "company_id"
CONF_PAGE_SIZE = "page_size"
CONF_VERIFY_SSL = "verify_ssl"

# Options
OPT_SCAN_INTERVAL = "scan_interval"
OPT_PAGE_SIZE = "page_size"
OPT_FETCH_PEOPLE = "fetch_people"
OPT_FETCH_CREDENTIALS = "fetch_credentials"
# Personal information on/off. Off = health and counts only: no names,
# e-mail addresses, member lists, per-person/per-credential entities or
# company contacts.
OPT_PERSONAL_DATA = "personal_data"

DEFAULT_SCAN_INTERVAL = 60  # seconds
DEFAULT_PAGE_SIZE = 100  # API maximum
DEFAULT_TIMEOUT = 30.0
DEFAULT_FETCH_PEOPLE = True
DEFAULT_FETCH_CREDENTIALS = True
# Entries created before this option existed keep their personal data.
# New entries get the choice in the config flow (unticked by default).
DEFAULT_PERSONAL_DATA = True

MIN_SCAN_INTERVAL = timedelta(seconds=15)

# Server-side rate limit: 120 requests/minute, GLOBAL across every API
# consumer (it protects the provisioning services). All NMA connections share
# one limiter that bursts at no more than half of it, and the
# people/credentials syncs share a small average budget.
RATE_LIMIT_MAX_REQUESTS = 60
RATE_LIMIT_PERIOD_S = 60.0
RATE_LIMIT_BACKOFF_S = 60  # every connection pauses this long after a 429
MAX_PAGE_SIZE = 100
# Average request budget for people/credentials syncs, shared by all NMA
# connections (each gets an equal part). A sync of N requests waits
# N * 60 / part seconds before the next one. With 4 connections (5/min each):
# 3 requests every poll, 158 requests (~8,800 people) about every 32 min.
LIST_SYNC_REQUESTS_PER_MIN = 20
LIST_SYNC_RETRY_S = 300  # after a failed sync (e.g. 429 from the shared limit)

PLATFORMS = ["sensor", "binary_sensor"]

SERVICE_REFRESH = "refresh"
ATTR_ENTRY_ID = "entry_id"

MANUFACTURER = "NMA"
MODEL = "Mobile Credentials API"
