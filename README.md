# NMA Mobile Credentials — Home Assistant integration

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/forgottenruntime/nma-home-assistant/main/custom_components/nma/brand/dark_logo@2x.png">
    <img src="https://raw.githubusercontent.com/forgottenruntime/nma-home-assistant/main/custom_components/nma/brand/logo@2x.png" alt="NMA Mobile Credentials" width="440">
  </picture>
</p>

A HACS-installable Home Assistant custom component that wraps the
[NMA API](../nma-api) and exposes a Company, its People and its Credentials as
Home Assistant entities. Built primarily as a **test/debug harness** for the API.

> Sibling project to [`nma-api`](../nma-api) which contains the OpenAPI spec
> and the Python client this integration vendors.

---

## Features

- Single config entry per **Company ID**, configured fully through the UI.
- **One device** per company, all entities grouped under it.
- **Connectivity watchdog**: `binary_sensor.*_api_reachable` is on while the
  most recent poll succeeded; attributes expose base URL, polling interval,
  last fetch duration, and last error message.
- **ACS WebSocket** binary sensor (`device_class: connectivity`) +
  `since` timestamp sensor + pending-message-count sensor.
- Company info sensors: name, status, type, ACS (`ATWORK`/`AEOS`),
  UAP migration status, enabled platforms, max-people, max-credentials,
  use-app-key, DF name, TCI value, tenant ID.
- **People** sensors: total count, plus counts per `PersonStatus`,
  per `Platform`, per `UapMigrationStatus`.
- **Credentials** sensors: total count, plus counts per `CredentialStatus`,
  per `Platform`, per `DeviceType`, per `UapMigrationStatus`.
- Every breakdown count sensor also carries a **`members` attribute** listing
  who is in that bucket (people: name/email/id/devices; credentials:
  number/person/id/device_type/platform/device), capped at 50 — so you can see
  *which* people are blocked, and *what device* (iPhone, Apple Watch, …) they
  carry, not just how many.
- **One sensor per Person** and **one per Credential** (disabled by default
  in the entity registry — enable from the device page when you need them).
- Diagnostic sensors: last successful update timestamp, last update
  duration in seconds.
- Action `nma.refresh` to poll on demand.
- Redacted **diagnostics download** from the device page (emails, names,
  tenant ID and contact blocks are stripped).

## Install

Pick the option that matches your setup. The fastest way to **just try it** is
the Docker quickstart below — it spins up a throwaway HA you can wipe with one
command.

### Option A — Quickstart with Docker (recommended for testing)

You need Docker Desktop (or Docker Engine) installed.

```bash
cd ~/nma-home-assistant
docker compose up -d
# wait ~30 seconds for first boot, then
open http://localhost:8123
```

Onboard with any name/password (it's a throwaway instance). Then:

**Settings → Devices & services → Add integration → NMA Mobile Credentials**

The integration source is bind-mounted **read-only** from this repo, so to
pick up code changes:

```bash
docker compose restart
```

To wipe HA and the integration config completely:

```bash
docker compose down -v
```

> macOS note: the bundled `compose.yaml` uses `network_mode: host` so HA can
> reach `127.0.0.1:8765` (the mock server). On Docker Desktop for Mac, host
> networking is best-effort — if `http://localhost:8123` doesn't load, edit
> `compose.yaml` (comment out `network_mode: host`, uncomment the `ports:`
> block) and use `http://host.docker.internal:8765` as the Base URL when
> pointing at the local mock server.

### Option B — Install into an existing Home Assistant

If you already run HA somewhere, the bundled script copies the integration in:

```bash
# Replace the path with your actual HA config directory (contains configuration.yaml).
~/nma-home-assistant/scripts/install.sh ~/homeassistant

# HA OS / Supervised over Samba:
~/nma-home-assistant/scripts/install.sh /Volumes/config

# Linux box where HA Container's /config is bind-mounted:
~/nma-home-assistant/scripts/install.sh /var/lib/homeassistant
```

The script verifies the target looks like an HA config directory, then rsyncs
`custom_components/nma/` into `<config>/custom_components/nma/`. Restart HA
afterwards (Settings → System → Restart, or `ha core restart` on HA OS).

### Option C — Manual install (no script)

Copy the folder yourself:

```
custom_components/nma/   →   <ha-config>/custom_components/nma/
```

Restart Home Assistant.

### Option D — HACS (once this repo is on GitHub)

1. Push this repo to GitHub.
2. In HA: **HACS → Integrations → ⋮ → Custom repositories**.
3. Paste the repo URL, category **Integration**.
4. Install **NMA Mobile Credentials**, restart HA.

The bundled `hacs.json` and `info.md` already declare the metadata HACS needs.

### Option E — Install on a remote HA over SSH

For an HA box you reach over SSH (HA OS with the **SSH & Web Terminal** add-on,
HA Container on a Linux server, ...) use the bundled remote-install script:

```bash
# Defaults to remote /config.
~/nma-home-assistant/scripts/install-remote.sh root@homeassistant.local:22222

# Custom config dir, e.g. on a generic Linux box:
~/nma-home-assistant/scripts/install-remote.sh user@homeserver ~/homeassistant
```

The script SSHes in, checks `configuration.yaml` exists at the target, then
`rsync`s `custom_components/nma/` over (deleting stale files). It prints the
restart command to run afterwards.

> The `host:port` form (e.g. `root@homeassistant.local:22222`) is converted to
> `ssh -p 22222` automatically. The HA OS SSH add-on listens on `22222` by
> default.

### Option F — Tarball drop-in (works everywhere)

If you can't SSH or run scripts, build a tarball and drop it in via Samba,
Studio Code Server, the File editor add-on, or `scp`:

```bash
~/nma-home-assistant/scripts/make_release.sh
# -> dist/nma-0.1.0.tar.gz   (15 KB)
```

On the HA box, extract straight into `/config/custom_components/`:

```bash
tar -xzf nma-0.1.0.tar.gz -C /config/custom_components/
```

The tarball unpacks as a single `nma/` folder, so nothing else in
`custom_components/` is touched.

---

### Add the integration in the UI

After installing by any method above and restarting HA:

**Settings → Devices & services → Add integration → NMA Mobile Credentials**

You'll be asked for:

| Field          | Notes                                                                |
|----------------|----------------------------------------------------------------------|
| Base URL       | Real API: `https://…` from the API owner. Mock: see below.           |
| Access token   | Bearer token — sent as `Authorization: Bearer <token>`.              |
| Company ID     | UUID. The flow calls `GET /api/admin/companies/{id}` to validate.    |
| Verify TLS     | Leave **on** for production. Off only for self-signed dev endpoints. |

The flow rejects invalid UUIDs, malformed URLs, and surfaces `401/403/404`
from the API as distinct errors.

## Options

After adding the entry, click **Configure**:

| Option              | Default | Notes                                                |
|---------------------|---------|------------------------------------------------------|
| `scan_interval`     | 60      | Polling interval in seconds (min 15, max 86400).     |
| `page_size`         | 50      | Per-page size for `/people` and `/credentials` (max 50, the API's recommendation). |
| `fetch_people`      | true    | Disable to skip the full `/people` pagination loop.  |
| `fetch_credentials` | true    | Same for `/credentials`.                             |

Disabling the two `fetch_*` toggles leaves you with just the Company and
WebSocket data — useful on huge companies where you only care about the
connection-alive signals.

## Rate limiting

The API enforces **30 requests/minute across all endpoints and environments**.
A single poll makes `1 + ceil(people/page_size) + ceil(credentials/page_size)`
requests, so a large company can exceed that in one poll.

The integration protects you automatically:

- A built-in **sliding-window limiter caps outgoing requests at 30/minute** and
  transparently waits (in a background thread) when the window is full — so a
  big paginated fetch is spread out rather than rejected.
- `page_size` is capped at **50** (the API's recommended maximum).
- If the server still returns **429**, it's surfaced as a clean
  *"Rate limit hit"* message and the next poll retries.

If you run **multiple config entries that share one token**, they share the real
30/min budget. In that case raise `scan_interval`, disable `fetch_people` /
`fetch_credentials` where you don't need them, or stagger the entries.

## Example dashboard

A ready-made Lovelace dashboard lives at
[`examples/lovelace-dashboard.yaml`](examples/lovelace-dashboard.yaml). It groups
the entities into **Company**, **Usage**, **Connectivity & health**, **Alerts**,
**Credentials**, **People**, **Individual credentials**, **Trends — recent**,
**Trends — long term** and **Diagnostics** sections, gives every tile a short
readable name, and uses dense section placement so the columns pack evenly.

Highlights:

- A **System status** header chip (green "all systems OK" or red "attention
  needed", listing the active problems) computed from connectivity + every
  problem counter — no HACS dependency, just a templated markdown card.
- **Usage gauges** for credentials and people (value vs limit, with green /
  amber / red bands) instead of a plain text total.
- An **Alerts** card listing the six example automations with their
  *last-triggered* time, so you can see at a glance which fired and when.
- A **Blocked / flagged** card that stays hidden until something is actually
  blocked, removed or migration-failed — then it appears and lists the affected
  people (name + email) and credentials (number + person), via a `conditional`
  card and the `members` attribute.
- An **Anonymise names** toggle that masks every first/last name on the
  dashboard to initials (e.g. *Gerald Kreditsch → G. K.*) and hides emails —
  handy when screen-sharing. Requires the `input_boolean.nma_anonymise` helper
  (see [`examples/helpers.yaml`](examples/helpers.yaml)).
- **Trends** split into recent history graphs and long-term statistics graphs,
  including a **People blocked / removed** trend (7-day history + 90-day stats)
  so you can see when access was revoked.
- A **Devices** card showing how many of each device type people carry (iPhone,
  Apple Watch, Android phone, Wear OS watch…) and who has a wearable. Labels are
  derived from the credential's `device_type` (PHONE/WEARABLE) + `platform`
  (APPLE/GOOGLE/UAP) — the API does not expose exact model names.

To use it: **Dashboard → Edit → ⋮ → Raw configuration editor**, paste it in, then
find-and-replace `red_bull_sandbox` with your own company slug (the slugified
device name) if it differs. The two gauges hard-code `max: 300` — set each to
your own `max_credentials` / `max_people`. The Alerts card assumes the example
automations are loaded (entity IDs are their slugified aliases).

### Anonymise toggle setup

The **Anonymise names** tile needs a one-time helper. Either add
[`examples/helpers.yaml`](examples/helpers.yaml) to your `configuration.yaml` and
restart, or create it in the UI: **Settings → Devices & Services → Helpers →
Create Helper → Toggle**, named so the entity becomes `input_boolean.nma_anonymise`.
When on, names render as initials and emails are hidden everywhere on the
dashboard; the underlying sensors and their `members` attribute are unchanged.

## Example automations / alerts

Many breakdown sensors normally read `0` — they become useful as **alerts** when
something goes wrong. [`examples/automations.yaml`](examples/automations.yaml)
ships six ready-to-use automations:

| Alert | Triggers when |
|-------|---------------|
| Credentials blocked | any credential is blocked by platform / ACS / person |
| UAP migration failed | a credential or person is in `MIGRATION_FAILED` |
| People blocked or removed | a person is blocked or removed by ACS |
| ACS WebSocket down | the WebSocket stays down for 5 minutes |
| API unreachable | polling fails for 10 minutes (includes last error) |
| ACS message backlog | pending messages stay above 50 for 10 minutes |

Each raises a **persistent notification** and also pushes to a phone via
`notify.mobile_app_bart_iphone15`. To target a different device, replace that
service name throughout the file; to drop phone push, delete the second
`notify.*` action in each automation. Paste them into **Settings → Automations &
scenes → ⋮ → Edit in YAML**, or append to your `automations.yaml`. Replace the
`red_bull_sandbox` slug as needed.

The example dashboard's **Trends** section also includes two `statistics-graph`
cards (totals over 90 days, ACS backlog over 30 days). These use Home
Assistant's **long-term statistics** — they survive recorder purges, so you keep
months of min/mean/max history at low storage cost.

## Test against the mock server

The companion repo ships [`examples/demo_mock.py`](../nma-api/examples/demo_mock.py),
an in-process mock server. The snippet below pins it to port `8765` on **all**
interfaces (`0.0.0.0`) so Home Assistant can reach it regardless of where HA
is running:

```bash
cd ~/nma-api
.venv/bin/python - <<'PY'
from http.server import HTTPServer
from examples.demo_mock import _Handler
HTTPServer(("0.0.0.0", 8765), _Handler).serve_forever()
PY
```

You should see `-> server received GET /api/admin/companies/...` lines whenever
HA polls.

In Home Assistant, add the integration with **one** of these Base URLs,
depending on where HA itself runs:

| HA runs on …                          | Base URL                                            |
|---------------------------------------|-----------------------------------------------------|
| The same Mac, native (HA OS in a VM)  | `http://<your-mac-LAN-IP>:8765` (e.g. `http://192.168.1.42:8765`) |
| The same Mac, in Docker               | `http://host.docker.internal:8765`                  |
| A separate device (Pi, NUC, …)        | `http://<your-mac-LAN-IP>:8765`                     |
| The same Python venv as the mock      | `http://127.0.0.1:8765`                             |

Find your Mac's LAN IP with `ipconfig getifaddr en0` (Wi-Fi) or `en1`
(Ethernet/Thunderbolt).

Other config-flow values for the mock:

- **Token:** anything (the mock ignores it).
- **Company ID:** `11111111-1111-1111-1111-111111111111` (hard-coded in the mock).
- **Verify TLS:** off.

All ~40 sensors should appear under the `Acme` device, with
`binary_sensor.acme_api_reachable` and `binary_sensor.acme_acs_websocket`
both `on`.

## Test against the real backend

The `nma-api` repo's [`openapi.yaml`](../nma-api/openapi.yaml) still ships
**placeholder server URLs** (`https://dev.api.example.com`,
`https://api.example.com`). Replace those with the real environment URL when
the API owner gives it to you, then in the HA config flow use:

- **Base URL:** the real `https://…` URL, no trailing slash.
- **Token:** a valid Bearer access token.
- **Company ID:** an existing company UUID at that endpoint.
- **Verify TLS:** leave **on** unless you're pointing at a self-signed staging
  endpoint.

The flow calls `GET /api/admin/companies/{id}` to validate before saving and
maps `401/403` → *invalid auth* and `404` → *company not found*.

## Service: `nma.refresh`

```yaml
service: nma.refresh
# Optionally restrict to one entry; otherwise refreshes all NMA entries
data:
  entry_id: "01HZ1234567890ABCDEF"
```

## Architecture

```
┌─────────────────────────┐
│ Home Assistant entity   │  sensor.* / binary_sensor.*
│   (CoordinatorEntity)   │
└─────────┬───────────────┘
          │ reads
┌─────────▼───────────────┐
│ NmaCoordinator          │  DataUpdateCoordinator
│  (scan_interval, ...)   │
└─────────┬───────────────┘
          │ await hass.async_add_executor_job(api.fetch_all)
┌─────────▼───────────────┐
│ NmaApi (sync)           │  thin wrapper, paginates /people + /credentials
└─────────┬───────────────┘
          │ requests.Session (Bearer token)
┌─────────▼───────────────┐
│ NMA API                 │
└─────────────────────────┘
```

## Caveats

- The vendored `nma_api` package requires **Pydantic v2.5+**. HA 2024.6+
  ships compatible versions.
- The integration runs the sync `requests`-based client in HA's thread
  executor. For large companies, consider lowering the scan interval and
  raising `page_size`.
- Per-Person/Per-Credential entities are *disabled by default* — they're
  intended for spot-checking the API, not as a production telemetry firehose.

## Troubleshooting

### `server_unavailable` / 502 / 503 / 504 when adding the integration

A `502 Bad Gateway` (or 503/504) means you **did** reach a server — a reverse
proxy / load balancer answered — but it could not reach the NMA API backend
behind it. This is a **server-side** condition; the integration cannot turn it
into a success. Diagnose from a shell (or the HA terminal add-on):

```bash
# Replace with the exact Base URL + a real company UUID you used.
curl -i -H "Authorization: Bearer <token>" \
  https://<your-base-url>/api/admin/companies/<company-uuid>
```

- **Still 502/503/504** → the backend is down, restarting, or the proxy is
  mis-routing. Wait and retry, or check with whoever runs the API. Confirm the
  Base URL points at the API host, not a generic web frontend.
- **200 + JSON** → the API is fine now; re-add the integration (it auto-retries
  on the next poll anyway).
- **401/403** → token problem. **404** → wrong company ID or path.

Since v0.1.3 the integration logs a concise `[502] Bad Gateway` instead of the
full HTML error page.

## Branding / logo

This integration ships its own brand images in
[`custom_components/nma/brand/`](custom_components/nma/brand) (`icon`, `logo`,
`dark_logo`, plus `@2x` variants). On **Home Assistant 2026.3+** these are
served by the local brands proxy at `/api/brands/integration/nma/icon.png`, so
the logo shows on the **Integrations page and device cards** — no
`home-assistant/brands` PR needed (that repo no longer accepts custom-integration
submissions).

> Note: the small icon in the **HACS store listing** may still appear blank.
> That's a known HACS bug ([hacs/integration#5171](https://github.com/hacs/integration/issues/5171))
> where HACS hasn't yet adopted the local brands proxy — unrelated to this
> integration. The HA UI itself shows the logo correctly.

To regenerate the artwork:

```bash
python3 scripts/make_brand.py
```

## License

[MIT](LICENSE) © Bart Vervueren.
