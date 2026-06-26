# Client Monitoring Dashboard — Home Assistant feasibility analysis

**Author:** Bart Vervueren
**Date:** 2026-06-26
**Subject:** Mapping the client's requested monitoring dashboard (mock-ups +
acceptance criteria) onto what a Home Assistant (HA) integration can deliver
today, and what is **blocked by the NMA API**.

> HA is used here as a **discovery / validation** tool: building the dashboard
> for real is the fastest way to prove which acceptance criteria are achievable
> and which depend on data the API does not (yet) expose. A production build may
> use different technology; the **API gaps are technology-independent** and are
> tracked in [`api-feature-requests.md`](api-feature-requests.md).

## Legend

| Mark | Meaning |
| --- | --- |
| ✅ | Buildable in HA today with the current integration (or a small addition). |
| 🟡 | Partially buildable — works with a caveat or an approximation. |
| ❌ | Not possible today — blocked by missing API data (see API ref). |

"API ref" points at the requirement in
[`api-feature-requests.md`](api-feature-requests.md).

---

## 1. Health indicators

| Requirement | HA | Notes | API ref |
| --- | --- | --- | --- |
| AEOS on-prem ↔ NMA SaaS connectivity | 🟡 | We expose `binary_sensor.*_acs_websocket` from `Company.acsWebSocket.up`. It is a single up/down boolean — fine as a connectivity light. | 2.4 |
| AEOS on-prem connection uptime | 🟡 | `acsWebSocket.since` gives "up since"; uptime % over a window needs the platform to report it (or HA approximates from its own history). | 2.4 |
| NMA SaaS uptime | 🟡 | We have an *API-reachable* watchdog (did our last poll succeed). That is **our** reachability, not the platform's true uptime/SLA. | 2.4 |
| NMA SaaS components running | ❌ | No per-component status in the API. | 2.4 |
| NMA SaaS API response times | 🟡 | We record poll **round-trip** duration (`sensor.*_last_update_duration`). That includes our network; it is not the server-side processing time. | 2.4 |
| Apple platform connectivity | ❌ | API exposes nothing about Apple-side health. | 2.4 |
| Apple platform API response times | ❌ | Same. | 2.4 |

**Summary:** the AEOS link and a coarse "can we reach the API" + round-trip
latency are available now. True SaaS/component/Apple health and server-side
latency require a platform **health endpoint** (API ref 2.4).

## 2. Alerts & notifications

| Requirement | HA | Notes | API ref |
| --- | --- | --- | --- |
| AEOS on-prem not reachable | 🟡 | Alert on `acsWebSocket` off. The API's single boolean can't separate "not reachable" from "reachable but not connected". | 2.4 |
| AEOS reachable but not connected | ❌ | Needs the two-state distinction from a health endpoint. | 2.4 |
| NMA SaaS downtime | 🟡 | Alert on the API-reachable watchdog (our view of it). | 2.4 |
| NMA components downtime | ❌ | Needs component status. | 2.4 |
| Latency > 500 ms on API calls | ✅ | We already ship an example automation pattern; alert when `last_update_duration > 0.5`. (This is round-trip latency.) | 2.4 |
| Apple platform not reachable | ❌ | No Apple health field. | 2.4 |
| Email notifications + incident-process triggers | ✅ | HA supports email/`notify.*` and webhooks to ticketing/incident tools. Already demonstrated with persistent + mobile-push alerts. | — |

## 3. Data visualization

| Requirement | HA | Notes | API ref |
| --- | --- | --- | --- |
| API response time line graph, 24 h → 1 year | ✅ | `history-graph` (recent) + `statistics-graph` (long-term, ~1 yr) on `last_update_duration`. (Round-trip latency; server-side needs 2.4.) | (2.4) |
| Healthy vs offline distribution chart | 🟡 | HA history of the connectivity binary sensors shows up/down over time; a true pie of % needs a template or a small custom card. | — |
| System errors **by type** (bar chart) | ❌ | No categorised error data in the API. | 2.5 |
| Users over time, per user type | ✅ | Implemented (v0.1.7): per-`personType` count sensors (Employee/Contractor/Visitor, discovered dynamically). Uses the free-text `personType.name`; a stable category (1.6) would make it more robust across renames. | (1.6) |
| Total users & per type | ✅ | Implemented (v0.1.7) as `sensor.*_people_<type>`. At very large scale a summary endpoint would still help. | (2.1) |
| Total users & per number of devices (0/1/2) | ✅ | Implemented (v0.1.7): `people_credentials_0/1/2/3plus` buckets from `Person.credentialCount`. | — |
| Total users & per device type | ✅ | We added device labels (iPhone/Apple Watch/…) in v0.1.6. | — |
| Total users & per **iOS version** | ❌ | API does not expose OS version (though your Devices UI shows it). | 1.1 |
| Total credentials & per state | ✅ | Already shipped (per-`CredentialStatus` sensors). | — |

## 4. Filters & customization

| Requirement | HA | Notes | API ref |
| --- | --- | --- | --- |
| Filter by error type | ❌ | No error data. | 2.5 |
| Filter by user type (employee/contractor/visitor) | ✅ | Implemented (v0.1.7): per-type count sensors for people and credentials; filter via separate cards. A stable category (1.6) would harden it. | (1.6) |
| Filter by credential state | ✅ | Per-state sensors already exist. | — |
| Filter by time range (hour…year) | ✅ | Built into HA history/statistics graphs. | — |
| Users customize widgets | 🟡 | HA dashboards are user-editable, but per-user *saved* layouts and locked widgets are limited (see §6). | — |

## 5. Performance — 30-second refresh

| Requirement | HA | Notes | API ref |
| --- | --- | --- | --- |
| Refresh every 30 s | ❌ (at scale) | Our `scan_interval` can be 30 s, **but** the API's 30 req/min limit + page size ≤ 50 means a full refresh of ~8,790 people + ~6,873 credentials is **~315 requests (~10 min)**. 30-second refresh is impossible without a **summary endpoint**, **delta sync**, or **webhooks**. | 2.1, 2.2, 2.3, 3.1 |

This is the single biggest blocker: the requested refresh rate is fundamentally
incompatible with the current API at the client's data volume.

## 6. User roles & permissions

| Requirement | HA | Notes |
| --- | --- | --- |
| Only authorized users access the dashboard | ✅ | HA authentication; dashboards can be restricted. |
| Only administrators configure | 🟡 | HA has admin vs non-admin users; admins edit dashboards. |
| "Viewer" role can see but not configure | 🟡 | HA's native role model is coarse (admin / user). Fine-grained "viewer cannot edit widgets/thresholds" typically needs extra setup or a different front-end. |

## 7. API access to KPIs

| Requirement | HA | Notes |
| --- | --- | --- |
| Dashboard metrics/KPIs via REST API | 🟡 | HA exposes all entity states/attributes via its own REST + WebSocket API and templates, so the KPIs we compute are queryable. If the requirement means the **NMA platform** must expose these KPIs directly, that maps to the summary/health endpoints (API refs 2.1, 2.4). |

## 8. Platform status, WebSocket, provisioning & history

Additional review items raised after the mock-ups.

| Requirement | HA | Notes | API ref |
| --- | --- | --- | --- |
| Platform healthiness | 🟡 | Only "can we reach the API" today; true health/components need an endpoint. | 2.4 |
| Platform uptime / availability | ❌ | No uptime figure exposed. | 5.1 |
| Last incident / incidents over time | ❌ | No incident data in the API. | 5.2 |
| Planned maintenance | ❌ | No maintenance-window data. | 5.3 |
| Apple services connectivity + uptime | ❌ | No Apple-side health. | 2.4, 5.1 |
| Google services connectivity + uptime | ❌ | No Google-side health. | 2.4, 5.1 |
| WebSocket response time | ❌ | `acsWebSocket` has no latency field. | 5.4 |
| WebSocket how long offline since up | 🟡 | HA can derive from its own history of the `up` flag. | (5.4) |
| WebSocket times offline over time | 🟡 | Same — HA counts state changes from history. | (5.4) |
| Provisioning live queue | 🟡 | Only `pendingMessagesCount` (a single backlog number); no queue detail. | 5.5 |
| Provisioning events & logs | ❌ | No event/log endpoint. | 5.5, 2.5 |
| Provisioning counts today / month / periods | ❌ | No timestamped provisioning data to aggregate. | 5.5 |
| Provisioning errors today / 24 h / week | ❌ | No categorised error feed. | 5.5, 2.5 |
| Badge pending / active / blocked | ✅ | Already shipped (per-`CredentialStatus` sensors). | — |
| Badge last time used | ❌ | No `lastUsedAt`. | 1.4 |
| Badge how many times used | ❌ | No usage count. | 1.8 |
| Relation user ↔ credential ↔ device | 🟡 | Buildable now via credential→person and device-type; "device" is a type, not a full device record (no model/serial). | (1.1) |
| Evolution over time vs previous period | 🟡 | HA charts evolution **going forward** (statistics, ~1 yr) and can compare periods with template helpers. **Historical backfill** (data from before HA started recording) needs a totals-history endpoint. | 2.6 |

**Net:** badge status counts and the user↔credential↔device-type relation are
available now; WebSocket "times/duration offline" and forward-looking evolution
are derivable from HA's own history. Everything else in this section — platform
uptime/incidents/maintenance, Apple/Google uptime, WebSocket latency,
provisioning queue/logs/throughput, badge usage, and true historical comparison
— requires the API additions referenced above.

---

## What we can deliver now (no API changes)

- AEOS link status + "up since"; API-reachable watchdog; round-trip latency.
- Latency-threshold and connectivity alerts; email/mobile/incident notifications.
- Credentials by state; people/credentials totals; device-type breakdown
  (iPhone/Apple Watch/…); users by credential-count (0/1/2/3+); users and
  credentials by person type (Employee/Contractor/Visitor).
- Recent + long-term (≈1 yr) trend graphs; time-range filtering.
- Authenticated access.

## What is blocked by the API (forward to supplier)

| Capability the client wants | Blocked by | API ref |
| --- | --- | --- |
| iOS-version buckets, exact model, serial | OS version / model / serial not in API (but in your Devices UI) | 1.1 |
| Accurate event timing, activation/deactivation dates | status-change timestamps not exposed (but in your UI) | 1.2 |
| Reliable user-type analytics & filtering | no stable personType category | 1.6 |
| 30-second refresh at scale | no summary endpoint / delta sync / webhooks; 30 req/min | 2.1–2.3, 3.1 |
| SaaS/component/Apple health + server latency | no health/metrics endpoint | 2.4 |
| "Errors by type" chart + filter | no categorised error/event feed | 2.5 |
| Real-time alerts (vs polling delay) | no push channel | 3.1 |

## Recommendation

1. Build the **achievable** subset in HA now (everything in *"deliver now"*) to
   validate UX and demonstrate value.
2. Forward [`api-feature-requests.md`](api-feature-requests.md) to the supplier;
   the **High** items (1.1, 1.2, 1.6, 2.1, 2.4, 3.1) unlock the majority of the
   remaining acceptance criteria.
3. Re-evaluate the 30-second refresh target with the supplier — it requires
   either a summary endpoint, delta sync, or a push channel.
