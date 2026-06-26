# NMA API — Feature & Data Requirements

**From:** Bart Vervueren
**Against:** NMA API `v1.0.0` (admin endpoints)
**Date:** 2026-06-26
**Status:** Request for comment / prioritisation

---

## Purpose

This document lists data and capabilities that a consuming client needs but the
current NMA API does not provide. Each item states **what** is needed, **why**,
a **suggested concrete shape** (field/endpoint), and the **workaround** (if any)
that exists today. Please review for feasibility and priority.

> **How this list was produced.** A monitoring client was built against the API
> to discover, empirically, what the API can and cannot do. The client itself is
> a prototyping/validation tool — a production deployment may use different
> technology — but the **gaps below are properties of the API**, independent of
> any particular client.
>
> Several gaps were confirmed by the supplier's **own** admin UI: its *Devices*
> view shows **OS version** and **serial number**, and its *People* / *Credentials*
> views show **deactivation/activation dates** and a **person type**
> (Employee / Contractor / Visitor) — none of which are exposed by the published
> API/spec. Where that is the case it is called out; it suggests the data exists
> internally and "only" needs to be surfaced through the API.

## Current API (for context)

Three read-only `GET` endpoints, scoped to a company:

| Endpoint | Returns |
| --- | --- |
| `GET /api/admin/companies/{id}` | `Company` |
| `GET /api/admin/companies/{companyId}/people` | `PeoplePaged` |
| `GET /api/admin/companies/{companyId}/credentials` | `CredentialsPaged` |

- **Rate limit:** 30 requests/minute across all endpoints and environments.
- **Recommended page size:** ≤ 50 items.
- `Credential.deviceType` ∈ `{PHONE, WEARABLE}`; `platform` ∈ `{APPLE, GOOGLE, UAP}`.
- All endpoints are read-only; there is no push/event channel for consumers.
- **Scale seen in production:** ~8,790 people and ~6,873 credentials for a single
  company. At page size 50 that is ~176 + ~138 ≈ **315 requests for one full
  refresh**, i.e. **~10 minutes** at 30 req/min. A 30-second refresh target is
  therefore impossible with the current API surface (see §2.1–2.3).

## Priority summary

| # | Requirement | Priority |
| --- | --- | --- |
| 1.1 | Device model, OS version & serial on `Credential` (shown in your own Devices UI) | High |
| 1.2 | Status-change / activation / deactivation timestamps | High |
| 1.5 | Consistent `creationDate` (spec vs behaviour mismatch) | High |
| 1.6 | `personType` category (Employee / Contractor / Visitor) on `Person` | High |
| 2.1 | Summary/aggregate endpoint (counts without full pagination) | High |
| 2.4 | Server-side health & latency metrics (SaaS, components, Apple, Google) | High |
| 3.1 | Webhooks / event stream for status changes | High |
| 5.1 | Platform uptime / availability metrics | High |
| 5.5 | Credential provisioning queue & throughput | High |
| 1.3 | Block/removal reason & actor | Medium |
| 1.4 | Credential last-used / last-active timestamp | Medium |
| 1.7 | `credentialCount` buckets / users-by-device-count | Medium |
| 1.8 | Credential usage count (how many times used) | Medium |
| 2.2 | Delta sync (`updatedSince` + `ETag`/`Last-Modified`) | Medium |
| 2.3 | Rate-limit headroom / `X-RateLimit-*` headers | Medium |
| 2.5 | System-error / event feed categorised by type | Medium |
| 2.6 | Historical totals / point-in-time snapshots (evolution over time) | Medium |
| 5.2 | Incident history (last incident, incidents over time) | Medium |
| 5.3 | Planned-maintenance schedule | Medium |
| 5.4 | WebSocket metrics (response time, downtime history) | Medium |
| 4.1 | Structured `429` body + `Retry-After` | Low |
| 4.2 | JSON error schema on `5xx` (not HTML) | Low |
| 4.3 | `personType` value documentation | Low |

> **Already achievable today (no API change needed) — for reference:** badge
> status counts (pending / active / blocked) are available now; the
> *user ↔ credential ↔ device-type* relation is exposed via credential/person
> attributes; and the consuming client can chart **its own** observed metrics
> over time (e.g. WebSocket up/down history → "times offline", and totals going
> forward) using its local history store. The items below are the gaps that the
> client **cannot** synthesise and that only the platform can provide.

---

## 1. Data fields

### 1.1 Device model, OS version & serial number — **High**
- **Today (published API):** `Credential.deviceType` only distinguishes `PHONE`
  vs `WEARABLE`, plus `platform` (`APPLE`/`GOOGLE`/`UAP`). No model, OS version,
  or serial number.
- **However:** the supplier's **own** admin *Devices* view already shows a
  **Device** type, an **OS Version** (e.g. `iOS 18.2`, `iOS 26.0`,
  `iOS 26.3 Beta 1`) and a **Serial Number** (e.g. `MR77K32KCQ`) per credential.
  So this data evidently exists — it is simply not exposed through the API.
- **Need:** expose those same fields through the API.
- **Suggested shape** — add to `Credential`:
  ```jsonc
  "device": {
    "modelName": "iPhone 15 Pro",      // human-readable, if available
    "modelIdentifier": "iPhone16,1",   // vendor identifier, if available
    "manufacturer": "Apple",
    "osName": "iOS",
    "osVersion": "18.2",               // already shown in your Devices UI
    "serialNumber": "MR77K32KCQ"       // already shown in your Devices UI
  }
  ```
- **Why:** asset tracking, support triage, and security policy — e.g. the client
  mock-up buckets devices as *“iOS 26 or higher”* vs *“Older iOS”*, which is only
  possible with `osVersion`.
- **Workaround:** we map `(platform, deviceType)` → a best-effort label
  (`iPhone`, `Apple Watch`, `Android phone`, `Wear OS watch`). Cannot show model,
  OS version or serial.

### 1.2 Status-change timestamps — **High**
- **Today:** `Person.status` and `Credential.status` expose only the *current*
  state. There is no record of *when* the state changed.
- **However:** the supplier's own *People* view shows a **Deactivation date**
  column and the *Credentials* view shows **Activation date** + **Deactivation
  date** — so these timestamps already exist internally.
- **Need:** expose those timestamps through the API.
- **Suggested shape** — add to `Person` and `Credential`:
  ```jsonc
  "statusChangedAt": "2026-06-26T08:00:00Z",   // ISO 8601 UTC
  "activatedAt":   "2025-09-22T00:00:00Z",      // credentials (“Activation date”)
  "deactivatedAt": null                         // “Deactivation date”, when applicable
  ```
- **Why:** audit/compliance and trend reporting. Today we can only chart when
  *our poller noticed* a change, not when it actually happened, and changes that
  occur and revert between polls are invisible.
- **Workaround:** poll every 60 s and infer the change time from the poll time
  (imprecise; misses sub-poll changes).

### 1.3 Block/removal reason & actor — **Medium**
- **Today:** statuses like `BLOCKED_BY_ACS` / `REMOVED_BY_ACS` carry no reason or
  actor.
- **Need:** why the change happened and who/what made it.
- **Suggested shape** — add to `Person`/`Credential`:
  ```jsonc
  "statusReason": "LOST_DEVICE",                // free text or enum
  "changedBy": { "id": "…", "name": "…", "type": "ADMIN|SYSTEM|ACS" }
  ```
- **Why:** answer "*who* blocked Gerald Kreditsch and *why*" — not possible today.

### 1.4 Credential last-used / last-active — **Medium**
- **Today:** no field indicating when a credential was last used (e.g. last door
  access).
- **Need:** `lastUsedAt` / `lastSeenAt` on `Credential`.
- **Why:** identify stale or unused credentials for clean-up; the client asks for
  a badge's *"last time used"*.

### 1.8 Credential usage count — **Medium**
- **Today:** no field counting how often a credential has been used.
- **Need:** a `usageCount` (and ideally a usage feed; see 5.5) on `Credential`.
- **Suggested shape** — add to `Credential`:
  ```jsonc
  "usageCount": 142,
  "lastUsedAt": "2026-06-26T07:55:00Z"
  ```
- **Why:** the client asks per badge for *"how many times used"*; not derivable
  from the current data.

### 1.5 Consistent `creationDate` (spec vs behaviour) — **High (data-consistency)**
- **Today:** the OpenAPI spec marks `Credential.creationDate` and
  `Person.creationDate` as **required**, but the live API (e.g. the Red Bull
  Sandbox tenant) returns items **without** `creationDate`. This breaks strict
  clients that validate against the published schema.
- **Need:** either always return `creationDate`, **or** update the OpenAPI spec
  to mark it optional, so spec and behaviour agree.
- **Why:** the mismatch caused hard validation failures on first integration.
- **Workaround:** we relaxed the field to optional on our side.

### 1.6 `personType` category on `Person` — **High**
- **Today:** `Person.personType` is an object with `id` + free-text `name`. The
  client mock-up needs to count and filter by a fixed set of categories
  **Employee / Contractor / Visitor** (the supplier's own People view shows
  exactly these).
- **Need:** a stable, enumerated person-type category so consumers can reliably
  bucket users by type (not by matching a free-text name).
- **Suggested shape** — add to `Person`:
  ```jsonc
  "personTypeCategory": "EMPLOYEE"   // EMPLOYEE | CONTRACTOR | VISITOR | OTHER
  ```
- **Why:** “users over time per user type”, totals per type, and the
  *filter by user type* requirement all depend on a stable category.

### 1.7 Users-by-device-count buckets — **Medium**
- **Today:** `Person.credentialCount` exists per person, so a client *can*
  bucket users as 0 / 1 / 2 credentials — but only after paginating all people.
- **Need:** either include these buckets in the summary endpoint (§2.1) or keep
  `credentialCount` (already present) and rely on the summary for totals.
- **Why:** the mock-up's “User with 0 / 1 / 2 Credential” tiles.

---

## 2. Aggregates & performance

### 2.1 Summary / aggregate endpoint — **High**
- **Today:** to display counts per status / platform / device type, we must fetch
  **all** people and **all** credentials (full pagination) on every refresh.
- **Need:** a single endpoint returning pre-computed counts.
- **Suggested shape:**
  ```
  GET /api/admin/companies/{companyId}/summary
  ```
  ```jsonc
  {
    "people":      { "total": 103, "byStatus": { "ACTIVE": 14, "INACTIVE": 87, "BLOCKED_BY_ACS": 2 } },
    "credentials": { "total": 9,   "byStatus": { "ACTIVE": 9 },
                     "byPlatform": { "APPLE": 9 },
                     "byDeviceType": { "PHONE": 7, "WEARABLE": 2 } }
  }
  ```
- **Why:** one cheap call instead of *N* paginated calls — critical for the
  30 req/min limit on large companies.

### 2.2 Delta / change sync — **Medium**
- **Need:** an `updatedSince` query parameter and standard caching headers
  (`ETag`, `If-Modified-Since`, `Last-Modified`) on the list endpoints.
- **Why:** avoid re-downloading entire lists each poll; reduces load and
  rate-limit pressure.

### 2.3 Rate-limit headroom / response headers — **Medium**
- **Today:** 30 req/min + page size ≤ 50 means a company with thousands of
  credentials needs many calls per refresh and can exhaust the limit.
- **Need:** one or more of:
  - a higher limit (or a dedicated read-only reporting tier),
  - a bulk export endpoint,
  - `X-RateLimit-Limit` / `X-RateLimit-Remaining` / `X-RateLimit-Reset` response
    headers so clients can self-throttle precisely.
- **Workaround:** we throttle client-side to 30/min with a sliding window.

### 2.4 Server-side health & latency metrics — **High**
- **Today:** there is no endpoint reporting the health of the platform itself.
  A consumer can only infer "reachable" by timing its own requests.
- **Need:** a health/metrics endpoint exposing, at minimum:
  - NMA SaaS overall up/down + per-**component** status,
  - **server-side** API response-time / latency metrics (p50/p95),
  - **Apple platform** connectivity + Apple API response times,
  - AEOS on-prem ↔ NMA SaaS link state with the *reachable-but-not-connected*
    distinction (today only a single `acsWebSocket.up` boolean exists).
- **Suggested shape:**
  ```
  GET /api/admin/health           // or /companies/{id}/health
  ```
  ```jsonc
  {
    "saas":   { "status": "UP", "components": { "provisioning": "UP", "acs-bridge": "DEGRADED" } },
    "apple":  { "status": "UP", "apiLatencyMs": { "p50": 120, "p95": 380 } },
    "google": { "status": "UP", "apiLatencyMs": { "p50": 110, "p95": 300 } },
    "api":    { "latencyMs": { "p50": 90, "p95": 250 } },
    "aeos":   { "reachable": true, "connected": true, "since": "2026-06-26T03:00:00Z" }
  }
  ```
- **Why:** the client mock-up's entire *Health Indicators* and *Alerts* sections
  (SaaS uptime, components running, API response times, Apple/Google connectivity,
  latency > 500 ms) depend on data only the platform itself can report. A
  consumer measuring its own round-trip cannot distinguish *its* network from
  *the platform's* health, nor see component-level or Apple/Google-side status.

### 2.5 System-error / event feed by type — **Medium**
- **Today:** no endpoint lists operational errors/events.
- **Need:** a categorised feed of system errors (e.g. connectivity issues,
  hardware failures, provisioning errors) with a `type`, `timestamp` and
  optional subject reference.
- **Suggested shape:**
  ```
  GET /api/admin/companies/{companyId}/events?since=…&type=…
  ```
  ```jsonc
  { "items": [ { "type": "PROVISIONING_ERROR", "at": "…", "credentialId": "…", "message": "…" } ] }
  ```
- **Why:** the mock-up's *"system errors by type"* bar chart and the *filter by
  error type* requirement.

### 2.6 Historical totals / point-in-time snapshots — **Medium**
- **Today:** all list/summary data is *current state only*. A consumer can chart
  totals **going forward** from the moment it starts recording, but cannot show
  the evolution of users/credentials **before** that, nor compare reliably
  against "yesterday / last week / last month / quarter / year".
- **Need:** either historical aggregate snapshots, or a time-series query.
- **Suggested shape:**
  ```
  GET /api/admin/companies/{companyId}/summary/history?from=…&to=…&interval=day
  ```
  ```jsonc
  { "series": [
    { "at": "2026-06-25", "people": 8788, "credentials": 6870, "byStatus": { "ACTIVE": 8713 } },
    { "at": "2026-06-26", "people": 8790, "credentials": 6873, "byStatus": { "ACTIVE": 8715 } }
  ] }
  ```
- **Why:** the client wants *"evolution of users / credentials over time,
  compared to previous day / week / month / quarter / half-year / year"*. The
  consumer can build this **prospectively** from its own history, but **period-
  over-period comparison with real history (and any backfill) needs the platform
  to retain and expose past totals**.

---

## 3. Real-time / push

### 3.1 Webhooks or event stream for status changes — **High**
- **Today:** no consumer-facing push channel; all data is pull-only.
- **Need:** a webhook (HTTP callback) or stream (SSE/WebSocket) emitting events
  when a person or credential changes state.
- **Suggested event shape:**
  ```jsonc
  {
    "type": "credential.status_changed",
    "companyId": "…",
    "credentialId": "…",
    "person": { "id": "…", "name": "…" },
    "from": "ACTIVE", "to": "BLOCKED_BY_ACS",
    "at": "2026-06-26T08:00:00Z"
  }
  ```
- **Why:** instant alerts (e.g. "person blocked") instead of up-to-60 s polling
  delay, accurate event timing for compliance, **and** it is the only way to meet
  the *30-second refresh* target at the observed scale (~8,790 people /
  ~6,873 credentials) without exceeding 30 req/min — push avoids re-polling
  entirely.
- **Note:** an ACS↔backend WebSocket already exists (`Company.acsWebSocket`); a
  customer-facing event feed would be its analogue.

---

## 4. Minor / robustness

### 4.1 Structured `429` body + `Retry-After` — **Low**
- When rate-limited, return a JSON `Error` body and a `Retry-After` header.
  We currently special-case non-JSON `429` responses.

### 4.2 JSON error schema on `5xx` — **Low**
- Gateway failures (`502`/`503`/`504`) returned an **HTML** error page rather
  than the documented `Error` schema. A JSON error even on gateway failures lets
  clients log a clean message instead of an HTML dump.

### 4.3 `personType` documentation — **Low**
- Clarify the allowed `personType` values and their meaning.

---

## 5. Platform status & observability

*These map to the client's "platform healthiness / uptime / incidents /
maintenance", WebSocket and provisioning-queue requirements. None are derivable
from the current API.*

### 5.1 Uptime / availability metrics — **High**
- **Today:** no uptime or availability figure for the platform, Apple, or Google
  services is exposed.
- **Need:** rolling uptime / availability % (e.g. 24 h / 7 d / 30 d) for: NMA
  SaaS overall, each component, the Apple platform, and the Google platform.
- **Suggested shape** — extend the health endpoint (2.4):
  ```jsonc
  "saas":   { "status": "UP", "uptime": { "24h": 100.0, "30d": 99.95 } },
  "apple":  { "status": "UP", "uptime": { "24h": 100.0, "30d": 99.9 } },
  "google": { "status": "UP", "uptime": { "24h": 100.0, "30d": 99.8 } }
  ```
- **Why:** client items *platform uptime / availability*, *Apple/Google services
  connectivity status and uptime*.

### 5.2 Incident history — **Medium**
- **Today:** no incident data.
- **Need:** the last incident and a list of past incidents (status-page style).
- **Suggested shape:**
  ```
  GET /api/admin/status/incidents?from=…&to=…
  ```
  ```jsonc
  { "lastIncident": { "id": "…", "title": "…", "impact": "MAJOR",
                     "startedAt": "…", "resolvedAt": "…" },
    "items": [ /* same shape, historical */ ] }
  ```
- **Why:** client items *last incident*, *incidents over time*.

### 5.3 Planned-maintenance schedule — **Medium**
- **Today:** no maintenance-window data.
- **Need:** upcoming/past planned-maintenance windows.
- **Suggested shape:**
  ```
  GET /api/admin/status/maintenance
  ```
  ```jsonc
  { "items": [ { "id": "…", "title": "…", "scheduledStart": "…", "scheduledEnd": "…",
                "components": ["provisioning"], "status": "SCHEDULED" } ] }
  ```
- **Why:** client item *planned maintenance*.

### 5.4 WebSocket metrics — **Medium**
- **Today:** `Company.acsWebSocket` exposes `up`, `since` and
  `pendingMessagesCount` only — no latency, and no downtime history.
- **Need:** WebSocket **response time / latency**, and downtime statistics
  (how long offline since last up; how many times offline over a window).
- **Suggested shape** — extend `acsWebSocket`:
  ```jsonc
  "acsWebSocket": {
    "up": true, "since": "…", "pendingMessagesCount": 0,
    "latencyMs": 35,
    "downtime": { "lastOutageDurationS": 0, "outages24h": 0, "outages30d": 2 }
  }
  ```
- **Note:** a consumer **can** approximate *"times offline"* and *"how long
  offline"* from its own history of the `up` flag, but **latency** and exact
  server-side downtime require the platform to report them.
- **Why:** client WebSocket items *response time*, *how long offline since up*,
  *how many times offline over time*.

### 5.5 Credential provisioning queue & throughput — **High**
- **Today:** the only provisioning signal is `acsWebSocket.pendingMessagesCount`
  (a single backlog number). There is no queue detail, no event log, and no
  throughput/error counts by period.
- **Need:**
  - a **live queue** view (depth + items being provisioned),
  - a **provisioning event log** with timestamps and outcome (success/error),
  - aggregate **throughput and error counts** by period (today / 24 h / week /
    month).
- **Suggested shape:**
  ```
  GET /api/admin/companies/{companyId}/provisioning/queue
  GET /api/admin/companies/{companyId}/provisioning/events?since=…
  GET /api/admin/companies/{companyId}/provisioning/stats?period=day
  ```
  ```jsonc
  { "queueDepth": 3, "inProgress": [ { "credentialId": "…", "since": "…" } ] }
  { "items": [ { "at": "…", "credentialId": "…", "event": "PROVISIONED", "durationMs": 820 } ] }
  { "period": "day", "provisioned": 412, "failed": 3, "errorsByType": { "APPLE_TIMEOUT": 2 } }
  ```
- **Why:** client *credential provisioning* items — live queue, events and logs,
  counts today / this month / other periods, and errors per period.

---

## How to read priorities

- **High** — blocks or significantly degrades a core use case (device identity,
  accurate audit timing, scalable polling, real-time alerts, or a spec bug).
- **Medium** — meaningful improvement; we have a working but suboptimal workaround.
- **Low** — robustness/quality-of-life.

*Prepared by Bart Vervueren. Happy to discuss concrete schemas or provide
sample payloads for any item.*
