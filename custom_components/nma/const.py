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

DEFAULT_SCAN_INTERVAL = 60  # seconds
DEFAULT_PAGE_SIZE = 50  # API recommends no more than 50 items per page
DEFAULT_TIMEOUT = 30.0
DEFAULT_FETCH_PEOPLE = True
DEFAULT_FETCH_CREDENTIALS = True

MIN_SCAN_INTERVAL = timedelta(seconds=15)

# Server-side rate limit: 30 requests/minute across all endpoints and
# environments. We throttle client-side to stay safely under it.
RATE_LIMIT_MAX_REQUESTS = 30
RATE_LIMIT_PERIOD_S = 60.0
MAX_PAGE_SIZE = 50

PLATFORMS = ["sensor", "binary_sensor"]

SERVICE_REFRESH = "refresh"
ATTR_ENTRY_ID = "entry_id"

MANUFACTURER = "NMA"
MODEL = "Mobile Credentials API"
