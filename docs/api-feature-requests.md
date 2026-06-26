# NMA API — Feature & Data Requirements

**From:** Home Assistant monitoring integration (`nma-home-assistant`)
**Against:** NMA API `v1.0.0` (admin endpoints)
**Date:** 2026-06-26
**Status:** Request for comment / prioritisation

---

## Purpose

This document lists data and capabilities our integration needs that the current
NMA API does not provide. Each item states **what** is needed, **why**, a
**suggested concrete shape** (field/endpoint), and the **workaround** we use
today. Please review for feasibility and priority.

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

## Priority summary

| # | Requirement | Priority |
| --- | --- | --- |
| 1.1 | Exact device model & OS version on `Credential` | High |
| 1.2 | Status-change timestamps on `Person` / `Credential` | High |
| 1.5 | Consistent `creationDate` (spec vs behaviour mismatch) | High |
| 2.1 | Summary/aggregate endpoint (counts without full pagination) | High |
| 3.1 | Webhooks / event stream for status changes | High |
| 1.3 | Block/removal reason & actor | Medium |
| 1.4 | Credential last-used / last-active timestamp | Medium |
| 2.2 | Delta sync (`updatedSince` + `ETag`/`Last-Modified`) | Medium |
| 2.3 | Rate-limit headroom / `X-RateLimit-*` headers | Medium |
| 4.1 | Structured `429` body + `Retry-After` | Low |
| 4.2 | JSON error schema on `5xx` (not HTML) | Low |

---

## 1. Data fields

### 1.1 Exact device model & OS version — **High**
- **Today:** `Credential.deviceType` only distinguishes `PHONE` vs `WEARABLE`,
  plus `platform` (`APPLE`/`GOOGLE`/`UAP`).
- **Need:** the concrete device, e.g. *iPhone 15 Pro* vs *iPhone SE*, or
  *Apple Watch Series 9*.
- **Suggested shape** — add to `Credential`:
  ```jsonc
  "device": {
    "modelName": "iPhone 15 Pro",      // human-readable
    "modelIdentifier": "iPhone16,1",   // vendor identifier
    "manufacturer": "Apple",
    "osName": "iOS",
    "osVersion": "18.2"
  }
  ```
- **Why:** asset tracking, support triage, security policy (e.g. minimum OS).
- **Workaround:** we map `(platform, deviceType)` → a best-effort label
  (`iPhone`, `Apple Watch`, `Android phone`, `Wear OS watch`). Cannot show model.

### 1.2 Status-change timestamps — **High**
- **Today:** `Person.status` and `Credential.status` expose only the *current*
  state. There is no record of *when* the state changed.
- **Need:** the timestamp of the last status transition.
- **Suggested shape** — add to `Person` and `Credential`:
  ```jsonc
  "statusChangedAt": "2026-06-26T08:00:00Z",   // ISO 8601 UTC
  "blockedAt":   "2026-06-26T08:00:00Z",        // optional, when applicable
  "removedAt":   null
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
- **Why:** identify stale or unused credentials for clean-up.

### 1.5 Consistent `creationDate` (spec vs behaviour) — **High (data-consistency)**
- **Today:** the OpenAPI spec marks `Credential.creationDate` and
  `Person.creationDate` as **required**, but the live API (e.g. the Red Bull
  Sandbox tenant) returns items **without** `creationDate`. This breaks strict
  clients that validate against the published schema.
- **Need:** either always return `creationDate`, **or** update the OpenAPI spec
  to mark it optional, so spec and behaviour agree.
- **Why:** the mismatch caused hard validation failures on first integration.
- **Workaround:** we relaxed the field to optional on our side.

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
  delay, and accurate event timing for compliance.
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

## How to read priorities

- **High** — blocks or significantly degrades a core use case (device identity,
  accurate audit timing, scalable polling, real-time alerts, or a spec bug).
- **Medium** — meaningful improvement; we have a working but suboptimal workaround.
- **Low** — robustness/quality-of-life.

*Prepared by the integration team. Happy to discuss concrete schemas or provide
sample payloads for any item.*
