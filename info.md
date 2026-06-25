# NMA Mobile Credentials

Home Assistant integration for the **NMA API** (mobile credentials).

Exposes a company, all its people and all its credentials as sensors so you can
inspect and watch the API live from Lovelace. Useful as a test/debug harness
for the API itself.

## Highlights

- One config entry per **Company ID**.
- Live **ACS WebSocket** connectivity binary sensor + pending-message count.
- **API reachable** binary sensor (connection-alive watchdog).
- Status breakdowns: counts per `CredentialStatus`, `PersonStatus`, `Platform`,
  `DeviceType`.
- Optional one-entity-per-person and one-entity-per-credential mode for
  deep inspection (disabled by default — they can be hundreds).
- `nma.refresh` service to poll on demand.
- Redacted diagnostics download.
