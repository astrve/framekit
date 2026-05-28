Read three files first, then targeted inspection.

Now map relevant code paths.

Plan-only task; no TaskCreate needed. Continue inspection.

Ignoring. Continue inspection — auth, settings, vault, web app routes, watch start path.

Acknowledged. Continue with new targets only.

Got enough. Writing plan.

---

# Framekit Service Mode — Architecture Plan

## 1. Current Architecture and Reusable Pieces

### What exists today

| Concern | Location | Storage | Notes |
|---|---|---|---|
| Settings | `core/settings/store.py` | `framekit.yaml` (platformdirs / project-local / `FRAMEKIT_CONFIG`) | filelock, YAML round-trip preserves comments. Shared between CLI/Web. |
| Profiles | `core/settings/profiles.py` | Same YAML + overlays | Active profile name persisted. |
| Vault | `core/security/vault.py` | `<config>/security/vault.enc` (Fernet) + `master.key` | Fail-closed contract. Stores TMDB token, image host keys, torrent-client password, provider tokens. |
| Webhooks | `core/webhooks.py` | `<config>/webhooks.json` | httpx POST in daemon thread. Events: `job.started`, `job.completed`, `job.failed`, `watch.file_detected`. |
| Aliases | `core/aliases.py` | YAML | CRUD only. |
| Run ledger | `core/runs/ledger.py` | `<config>/runs/ledger.ndjson` | NDJSON, append-only. Drives `rollback`. |
| Job runner | `web/modules.py` | `<cache>/web/module_jobs.sqlite3` | One table `web_module_jobs(id, created_at, status, payload_json)`. ThreadPoolExecutor max_workers=2. Pending/running jobs marked failed on restart. |
| Subprocess shim | `core/subprocess_safe.py` | n/a | `popen_safe` / `run_safe`. Env `NO_COLOR=1`, `FRAMEKIT_WEB_JOB=1`. |
| Watch | `modules/watch/service.py` + `commands/watch.py` | `.framekit_watch.pid` in CWD | `watchfiles` lib. Per-process. SIGTERM / CTRL_BREAK_EVENT. |
| Watch via Web | `web/app.py:654` | n/a | Wraps `watch start --all` in a 7200s web job. Dies on backend restart or timeout. |
| Auth | `core/auth/` | `<config>/users.db` | bcrypt + JWT HS256. Opt-in by user-count. |
| FastAPI app | `web/app.py:328 create_app()` | n/a | Single-file routes, in-process. No `framekit web` Click command exposed. |
| Webhooks dispatcher | inline in `modules.py:1765/1800/1826` | n/a | Fired from job runner — already a "service event bus" of sorts. |

### Already reusable for service mode

- SettingsStore (file-locked YAML) → shared config layer.
- Vault → secrets storage already isolated.
- Webhooks `dispatch_webhook_event` → event bus primitive.
- `enqueue_module_job` + sqlite persistence → queue primitive (single-process only).
- Run ledger → durable action log.
- Watch service core (`WatcherService`) → folder→preset routing engine.
- `popen_safe` → subprocess execution.

### What blocks "service mode" today

1. Watch start path goes through web job runner with 2h cap, not a long-lived supervised daemon.
2. Web backend and Watch daemon are independent processes with no shared lifecycle, no IPC. Web "controls" Watch only by spawning a child of itself.
3. Job queue is in-process only; if uvicorn dies, queue dies. SQLite persistence is for restart-recovery audit only, not work resumption.
4. No intake API. External downloaders can only drop files in watched folders.
5. No service-mode CLI entry (`framekit serve`, `framekit service install`).
6. No supervisor — when watch crashes, nothing restarts it.

---

## 2. Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  framekit service (single long-running process)                 │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Supervisor / async main loop                          │    │
│  │  - lifecycle of all sub-components                     │    │
│  │  - graceful shutdown                                   │    │
│  │  - restart on internal subsystem failure               │    │
│  └────────────────────────────────────────────────────────┘    │
│        │              │              │              │           │
│  ┌─────▼────┐  ┌──────▼─────┐ ┌──────▼─────┐ ┌──────▼──────┐  │
│  │ FastAPI  │  │ Watcher    │ │ Job Queue  │ │ Webhook /   │  │
│  │ HTTP API │  │ + Intake   │ │ Worker     │ │ Event Bus   │  │
│  │ (uvicorn)│  │ Producer   │ │ Pool       │ │             │  │
│  └──────────┘  └────────────┘ └────────────┘ └─────────────┘  │
│        │              │              │              │           │
│  ┌─────▼──────────────▼──────────────▼──────────────▼──────┐  │
│  │ Shared state layer                                       │  │
│  │ - SettingsStore (file-locked YAML)                       │  │
│  │ - Vault (Fernet)                                         │  │
│  │ - Jobs DB (SQLite, claim-based queue)                    │  │
│  │ - Run ledger (NDJSON)                                    │  │
│  │ - Events ring buffer (in-memory + log file)              │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
        ▲                                  ▲
        │ HTTP                             │ FS / HTTP
        │                                  │
┌───────┴──────────┐         ┌─────────────┴────────────┐
│  Web UI          │         │  External downloaders    │
│  CLI (read+write)│         │  (qBittorrent, custom)   │
└──────────────────┘         └──────────────────────────┘
```

### Single-process service

One OS process hosting:
- FastAPI HTTP API (uvicorn worker(s)=1 — single writer).
- File watcher subsystem (replaces standalone watch daemon).
- Job worker pool (replaces in-process ThreadPoolExecutor).
- Event bus / webhook dispatcher.
- Optional intake HTTP endpoint(s).

### CLI keeps two modes

- **Ad-hoc CLI** (today's behavior): one-shot invocations using same settings. Independent of service.
- **Service control CLI**: `framekit service {start|stop|status|install|uninstall}` — talks to service via OS service manager (Windows SCM / systemd) and/or HTTP.

### Web UI keeps shared YAML/vault

Web UI mutates settings through API → service applies them → CLI reads same files when run later. Same as today, but service now also re-reads on demand.

---

## 3. Core Service Responsibilities

The service process owns:

1. **Watch loop**
   - Reads `settings.watch.folders` from YAML.
   - Reconciles desired vs running watchers on config change (signal or polled).
   - For each enabled folder: detect new files via `watchfiles` → enqueue job with preset.
   - Emits `watch.file_detected` event.

2. **Job queue + worker pool**
   - Pull next pending job from SQLite jobs DB (claim with `UPDATE … WHERE status='pending' LIMIT 1` + `RETURNING`).
   - Spawn subprocess via `popen_safe` (existing path).
   - Stream live_stdout/live_stderr → DB rows.
   - Mark completed/failed, fire webhook events.
   - Honor `concurrency` setting per category (transform / upload / transfer).

3. **Intake**
   - HTTP endpoint accepts release-ready notification → creates job(s) using preset/profile.
   - Optional folder-drop intake (already the watch case).

4. **Status surface**
   - `/api/v1/service/status` — uptime, queue depth, watch counts, last error.
   - Live event stream (SSE or long-poll) for Web UI.

5. **Webhook dispatcher** (already exists, keep).

6. **Process supervisor**
   - On internal subsystem crash (e.g. watcher thread dies): log + restart that subsystem, not the whole process.
   - On unrecoverable error: exit non-zero so OS service manager restarts.

7. **Settings change reaction**
   - SettingsStore mutation → service notices (via in-process pub/sub) → reconfigure watchers, workers, webhooks live. No restart needed for trivial changes.

---

## 4. CLI Responsibilities

CLI remains the authoritative one-shot tool. No behavior change to existing commands.

### New CLI surfaces

| Command | Purpose |
|---|---|
| `framekit serve` | Run service in foreground (development, Docker). Equivalent to `uvicorn` + supervisor. Honors `--host`, `--port`, `--workers=1`. |
| `framekit service install` | Register as Windows service (via NSSM or native `sc.exe`) or write systemd unit. Print next-steps. |
| `framekit service uninstall` | Remove OS service entry. |
| `framekit service start/stop/restart/status` | Wrapper that talks to OS service manager. Falls back to HTTP `/service/status` for status when manager unavailable. |
| `framekit service logs` | Tail service log file. |

### Existing watch CLI behavior

- `framekit watch start` keeps working as foreground watcher for users who want ad-hoc watching without a service.
- Long-term, this becomes a thin client that hits `/api/v1/service/status` when a service is running and offers to defer to it.
- Do not break or remove the existing in-process watcher.

### CLI ↔ service contention

- CLI subprocess jobs (e.g. user runs `framekit pipeline X` manually) do **not** go through the service queue. They write to the run ledger and to subprocess logs as today.
- This is acceptable; release pipelines run by humans are by design ad-hoc.

---

## 5. Web UI Responsibilities

Web UI is control + monitoring, never the runtime.

### Service-aware pages

- **Service Status** (new card on dashboard): running / stopped, uptime, PID, queue depth, watch folders active, last error.
- **Watch** page (already planned in WEB_UI_V1_PLAN.md Batch J): folders + start/stop. Start/stop now hit `/api/v1/service/start|stop` (talks to OS service manager), not a 2h subprocess.
- **Jobs**: still shows the queue (now persistent and resumable).
- **Events**: new live stream (SSE) of events (watch.file_detected, job.started, job.completed, webhooks dispatched).
- **Settings**: unchanged — still mutate YAML / vault.

### Coexistence with no-service mode

- If the service is not running, the Web UI degrades:
  - Existing in-process job runner still works (today's behavior).
  - Watch service status card shows "service not running — install with `framekit service install`".
  - No intake endpoints.

---

## 6. Data / Storage Model

Existing locations stay. One new column / DB needed.

### Filesystem layout (unchanged unless noted)

```
<config_dir>/                          (platformdirs / FRAMEKIT_CONFIG_DIR)
├── framekit.yaml                       Settings (CLI + service + Web UI share)
├── webhooks.json                       Webhooks
├── users.db                            Auth (sqlite)
├── runs/
│   └── ledger.ndjson                   Reversible operations
├── security/
│   ├── vault.enc                       Fernet vault
│   └── master.key                      Vault key (fallback)
├── service/                            NEW
│   ├── service.pid                     Single PID file for the running service
│   ├── service.lock                    Cross-process startup lock
│   ├── service.state.json              Last-known status snapshot
│   └── events.ndjson                   Rolling event log (rotated, e.g. 50 MB)

<cache_dir>/
├── web/
│   └── module_jobs.sqlite3             Existing — extended schema below
├── intelligent/                        Existing metadata caches
└── metadata_cache.json                 Existing
```

### Jobs DB — extended schema

Add columns to existing `web_module_jobs` (additive migration):

| Column | Type | Purpose |
|---|---|---|
| `id` | TEXT PK | Existing |
| `created_at` | TEXT | Existing |
| `status` | TEXT | Existing — adds `claimed`, retains `pending/running/completed/failed/cancelled` |
| `payload_json` | TEXT | Existing |
| `priority` | INT default 0 | Higher first |
| `claimed_by` | TEXT NULL | Worker id |
| `claimed_at` | TEXT NULL | For stale-claim recovery |
| `category` | TEXT NULL | `transform` / `upload` / `transfer` / `inspect` — for concurrency caps |
| `origin` | TEXT NULL | `cli`, `web`, `watch`, `intake:<source>` |
| `request_hash` | TEXT NULL | Dedup hint for intake |
| `attempts` | INT default 0 | Retry counter |

Indexes: `(status, priority DESC, created_at)`, `(category, status)`, `(request_hash)` for dedup.

### Events ring buffer

Append-only NDJSON, rolling. Each event: `{ts, type, module?, job_id?, path?, level, msg, data}`. Drives SSE stream + Webhooks (which already consume same event names).

### No new vault format

Sensitive values used by intake (API keys for downloader callbacks, if any) go in existing Vault under namespaced keys (`intake.<source>.token`).

---

## 7. Process / Lifecycle Model

### Windows (first)

Two install paths supported; user picks one.

| Path | Tool | When |
|---|---|---|
| **Service** | `sc.exe` + a hosting shim, or NSSM (preferred — handles stdout/stderr redirection, restart-on-fail, log rotation). Bundle NSSM if license allows; else require user to install. | Always-on, runs at boot, multi-user host. |
| **Scheduled Task** | `schtasks.exe`, trigger "At log on" | Single-user laptop. Simpler, no admin requirement. |

#### Windows lifecycle

1. `framekit service install` → writes:
   - Service definition (NSSM `nssm install Framekit <python> -m framekit serve --service`).
   - `Start=auto`, recovery actions: restart on failure (1st/2nd: 60s).
   - Service runs as LocalService by default; user can switch via NSSM GUI.
   - Logs piped to `<config>/service/service.out.log` and `service.err.log`.
2. Service start → `framekit serve --service`:
   - Acquire `service.lock`. Refuse if already held.
   - Write `service.pid`.
   - Init SettingsStore, Vault, Job DB, Watcher, FastAPI, Webhook bus.
   - Bind uvicorn on `127.0.0.1:<port>` (default 7848 — pick once, document).
   - Heartbeat thread updates `service.state.json` every 5s.
3. Stop signal → SCM sends `SERVICE_CONTROL_STOP` → service drains in-flight jobs (configurable timeout) → flushes ledger → releases lock → exits 0.
4. Stop fallback: `taskkill /PID <pid>` reads `service.pid`.

#### Watch reconciliation on Windows

Replace the project-local `.framekit_watch.pid` model for the service. Service owns one single watcher subsystem internally; PID file no longer needed for watch. The ad-hoc `framekit watch start` foreground mode still uses the legacy PID file unchanged.

### Linux / Docker (later — Phase S5)

| Mode | Mechanism |
|---|---|
| systemd | `framekit service install` writes user-unit `~/.config/systemd/user/framekit.service`. `ExecStart=framekit serve --service`. `Restart=on-failure`. |
| Docker | `docker run -v <config>:/config -v <media>:/media -p 7848:7848 framekit:latest serve --service`. Image entrypoint = `framekit serve --service`. |
| Linux daemon (no systemd) | Same `framekit serve --service` foreground, user supervises. |

Same lock + pid file + state file layout; only the supervisor differs.

### Single-writer invariant

Across all platforms: at most one service process per `<config_dir>`. Enforced by exclusive `service.lock` (filelock). CLI ad-hoc runs do not take this lock — they coexist by writing to ledger + jobs DB but never claim a worker slot.

---

## 8. API Design

All under `/api/v1`. Auth applies when users exist (existing behavior). Service-specific routes refuse cleanly when service mode not active.

### 8.1 Service status / control

```
GET  /api/v1/service/status
  → {
      mode: "service" | "ephemeral",
      running: bool,
      pid: int | null,
      uptime_seconds: int,
      version: str,
      host: "127.0.0.1",
      port: int,
      subsystems: {
        watcher: {state, folders_active, files_in_queue, last_event_ts},
        worker:  {workers_running, queue_pending, queue_running, last_job_ts},
        webhook: {dispatched_total, failures_recent},
        intake:  {enabled, accepted_total, rejected_total}
      },
      last_error: {ts, msg} | null
    }

POST /api/v1/service/reload     (admin)  → reload settings, reconcile watchers
POST /api/v1/service/drain      (admin)  → stop accepting new jobs, finish running
POST /api/v1/service/shutdown   (admin)  → graceful exit (SCM still primary)
```

Start is **not** an HTTP endpoint — only OS service manager can start the service. The Web UI exposes a button that runs `framekit service start` via a tiny privileged helper or instructs the user. Reason: starting a process from inside a web request that is itself supposed to be that process is incoherent.

### 8.2 Queue / Jobs

Extends today's `/api/v1/modules/jobs`. Backward compatible.

```
POST   /api/v1/modules/jobs                     (existing) — enqueue
GET    /api/v1/modules/jobs                     (existing) — list
GET    /api/v1/modules/jobs/{id}                (existing) — detail
DELETE /api/v1/modules/jobs/{id}                (existing) — cancel
POST   /api/v1/modules/jobs/{id}/rerun          (existing)

GET    /api/v1/jobs/queue                       NEW       → {pending, running, by_category}
POST   /api/v1/jobs/{id}/priority               NEW       → {priority: int}
POST   /api/v1/jobs/{id}/pause                  NEW       (queue-level only, before claim)
POST   /api/v1/jobs/{id}/resume                 NEW
```

### 8.3 Watch folders / rules

```
GET    /api/v1/watch/folders                    (existing)
POST   /api/v1/watch/folders                    (existing)
DELETE /api/v1/watch/folders/{index}            (existing)
GET    /api/v1/watch/service                    (existing) — now returns rich subsystem state
POST   /api/v1/watch/service/start              REPLACED  → 409 if service mode; honors service control instead
POST   /api/v1/watch/service/stop               REPLACED  → same

GET    /api/v1/watch/rules                      NEW       — currently 1 rule = 1 folder. Future-friendly route.
POST   /api/v1/watch/rules                      NEW       — folder + preset + filter (regex on filename)
PATCH  /api/v1/watch/rules/{id}                 NEW       — toggle, change preset
DELETE /api/v1/watch/rules/{id}                 NEW
```

Phase 1 keeps `/api/v1/watch/folders` as the only writer; `/rules` is a planned superset for once filters land.

### 8.4 Intake (external downloaders)

```
POST   /api/v1/intake/release                   NEW
  body: {
    source: "qbittorrent" | "deluge" | "custom",
    path: str,                  // local path the service can read
    name: str | null,           // hint
    preset: str | null,         // override watch preset
    profile: str | null,        // override settings profile
    dedup_key: str | null,
    metadata: { ... }           // free-form
  }
  auth: API key (vault: intake.<source>.token) OR JWT
  → { job_id, accepted: bool, dedup_hit: bool }

POST   /api/v1/intake/webhook/{source}          NEW   — alias with preset source identity
GET    /api/v1/intake/sources                   NEW   — list configured intake sources
POST   /api/v1/intake/sources                   admin — create source + generate token
DELETE /api/v1/intake/sources/{id}              admin
```

Behavior:
- Verifies path exists and is under an allowlisted root (`settings.intake.allowed_roots`, defaulting to watch folders).
- Computes `request_hash = sha1(source + path + dedup_key or path)`; if a job with that hash is pending/running, returns `dedup_hit: true` with that job id.
- Selects preset: explicit → source default → match against watch rule for that path → fail.
- Enqueues a `pipeline` (or configured workflow) job with `origin=intake:<source>`.

Security: never accept arbitrary commands here. Intake creates pipeline jobs only, never raw subprocess invocations.

### 8.5 Logs / events

```
GET   /api/v1/logs/read                         (existing) — log file tail
GET   /api/v1/events/stream                     NEW       — SSE stream of service events
GET   /api/v1/events/recent?limit=200           NEW       — last N from ring buffer

Event types:
  service.started, service.stopped, service.error
  watch.file_detected, watch.folder_added, watch.folder_failed
  job.queued, job.started, job.completed, job.failed, job.cancelled
  webhook.sent, webhook.failed
  intake.received, intake.rejected
```

Same names already wired to webhook dispatcher → unification.

---

## 9. Migration from Current Watch Session Implementation

### Today's behavior (problematic)

- `POST /api/v1/watch/service/start` enqueues a module job with `module=watch args_text="start --all --no-status-updates"` and a **7200 s timeout**.
- Runs inside the web backend's job thread pool. If backend restarts, watch dies (job marked failed).
- `framekit watch start` from CLI writes `.framekit_watch.pid` to CWD — directory-scoped, easily orphaned.

### Migration steps (no breaking changes for CLI users)

1. **Keep** `framekit watch start` foreground mode and its CLI flow exactly as-is. CLI users without a service installed see no change.
2. **Replace** the web's `/watch/service/start` implementation:
   - When `mode=service`: route returns 409 + instruction to use `framekit service start`.
   - When `mode=ephemeral` (no service installed yet, today's reality): keep current 2h spawn behavior so we don't ship a regression — but log a deprecation warning and surface "install service" CTA in Web UI.
3. **Move** watch subsystem from "started as a child of the web backend job runner" to "subsystem inside the service process". The web app inside the service does not re-spawn watch; it just reads watcher subsystem state from the supervisor.
4. **Decouple** the watcher PID file from `.framekit_watch.pid` in CWD:
   - Service mode: watcher state lives in the service itself; no PID file.
   - Standalone CLI watch: keep `.framekit_watch.pid` for backward compat.
5. **Preserve** the existing `WatcherService` engine; only its host changes. `_setup_signal_handlers` already skips when not in main thread → good for embedding.
6. **Webhooks** already emit `watch.file_detected` — keep call site, just emitted from the service-owned watcher instead.

### Settings shape — no migration needed

`settings.watch.folders` schema unchanged. The service consumes the same list.

---

## 10. Implementation Roadmap

### Phase S1 — Durable service core (highest value, smallest blast radius)

**Goal:** A single `framekit serve --service` process that hosts the existing FastAPI app + a real watcher subsystem + a claim-based job worker, with one lock and one PID file. No new APIs yet, no intake.

Work:
1. Add `framekit serve` click command in `src/framekit/commands/`. Loads `web.app:create_app`, runs uvicorn programmatically with `workers=1`.
2. Add `core/service/supervisor.py`:
   - On startup: acquire `service.lock`, write `service.pid`, init SettingsStore, Vault, Jobs DB migration.
   - Spawn watcher subsystem as in-process threads (`WatcherService.start()` minus `signal.signal` path — already supported).
   - Spawn job worker pool (replaces ThreadPoolExecutor): N threads pulling claimed jobs from SQLite.
3. Migrate `web_module_jobs` schema additively (priority, claimed_by, claimed_at, category, origin, request_hash, attempts).
4. Convert `enqueue_module_job` to insert-only (status=pending); workers claim by `UPDATE … RETURNING`.
5. On startup: re-claim or reset `claimed` rows whose `claimed_by` matches the dead worker (orphan recovery) — generalize today's "mark pending/running as failed" path.
6. Service main loop: heartbeat → `service.state.json`.

Files touched (estimate):
- `commands/main.py` (register serve), `commands/serve.py` (new), `core/service/supervisor.py` (new), `core/service/worker.py` (new), `web/modules.py` (queue + claim refactor), small migration helper.

Risk: medium. Concurrency in SQLite needs WAL mode + correct claim semantics. Watcher embedding already supported by `WatcherService`.

### Phase S2 — Web UI status + control

**Goal:** Web UI reflects service mode accurately. No new behavior beyond visibility.

Work:
1. `/api/v1/service/status` route returning subsystem snapshot.
2. Dashboard card "Service" (running, uptime, queue depth, last error).
3. Watch page: change start/stop to surface "service handles watching automatically" when service is active; preserve current ephemeral spawn when no service installed.
4. SSE `/api/v1/events/stream` + Web UI subscribes for live job updates instead of polling. Optional in S2, can defer.
5. Jobs page: show `origin`, `category`, `priority` columns.

Backend code already 80% present; mostly wiring + UI.

### Phase S3 — Intake API

**Goal:** External downloaders trigger releases via HTTP.

Work:
1. `POST /api/v1/intake/release` and `intake_sources` admin CRUD.
2. Source token storage in vault under `intake.<source>.token`.
3. Allowlisted roots in `settings.intake.allowed_roots`.
4. Dedup via `request_hash` index.
5. Preset/profile resolution rules.
6. Per-source rate limiting (basic, per-IP+token, 30 req/min default).
7. Documentation example for qBittorrent "Run external program on torrent finished" pointing at `curl … intake/webhook/qbittorrent`.

### Phase S4 — Windows service / scheduled task

**Goal:** Easy install on Windows.

Work:
1. `framekit service install` Click command. Two flavors:
   - `--mode=service` (NSSM if present, else `sc.exe`).
   - `--mode=task` (`schtasks /Create /TN Framekit /TR "..." /SC ONLOGON`).
2. Detect NSSM availability; if missing, link instructions and fall back to scheduled task with a warning.
3. `framekit service status` reads SCM via `sc query Framekit` (subprocess); fall back to HTTP `/service/status`.
4. Log file rotation policy (handed off to NSSM rotation or our own simple sized rotator).
5. Restart-on-failure recovery actions configured at install time.

### Phase S5 — Linux / Docker

**Goal:** Cross-platform parity.

Work:
1. systemd user-unit generator (`framekit service install` on Linux).
2. Dockerfile + compose example. Volumes: `<config>`, media roots. Healthcheck = `curl /healthz`. Default user-id mapping for media.
3. Documentation for non-systemd Linux (foreground `framekit serve`).

---

## 11. Risks and Test Strategy

### Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Two writers to YAML / vault (service + ad-hoc CLI) | High | Existing filelock already covers this. Add stress test. |
| SQLite claim race under high concurrency | Med | WAL mode, `BEGIN IMMEDIATE`, `UPDATE … RETURNING` semantics; cap worker count low (2-4). Tested under N=8 parallel claimers. |
| Watcher subsystem crash takes whole process down | High | `WatcherService.start()` runs in a supervised thread; on exception, log + restart that thread N times with backoff, then mark watcher subsystem unhealthy in `/service/status`. Do not kill process. |
| Long-running job survives backend restart | Med | Already partial: today we mark stale jobs failed. Improve to "re-enqueue if `attempts<max_attempts` and origin=watch". |
| Windows service permission for media paths | High | Document running service as user account, not LocalService, when accessing user folders. Install command surfaces this. |
| Intake DDoS / path traversal | High | Allowlist roots, normalize paths with `Path.resolve()` + `is_relative_to`, rate limit, require token, audit-log every intake. |
| Webhook secrets / intake tokens leak in logs | High | Existing redaction code in `redact_settings`; extend to intake source tokens. |
| CLI ad-hoc runs and service stepping on same release | Med | Run ledger already records actions; document precedence; future: optional intake-side lock on release path. |
| First-class auth when service exposed beyond localhost | Med | Default bind `127.0.0.1`. Refuse `0.0.0.0` unless `auth.enabled=True` AND at least one admin exists. |

### Test strategy

1. **Unit**
   - SQLite claim logic (single-claim under concurrency).
   - Settings reload reconciliation (add/remove/disable folder while running).
   - Intake path validation (traversal, allowlist).
   - Webhook event emission for each lifecycle transition.
2. **Integration**
   - Spawn `framekit serve --service` in subprocess against tmp config dir.
   - Drop files in watched folder → assert job created → assert job completes with mocked CLI subprocess (or via a no-op preset).
   - POST intake → job created → webhook fired.
   - Kill service mid-job → restart → assert orphan recovery (job either resumed or marked failed deterministically per `attempts`).
3. **Lifecycle**
   - Windows: install service via NSSM in CI (skipped on PRs, smoke job nightly), assert start/stop/restart works.
   - Linux: same with systemd user-unit (in container).
   - Docker: compose-up smoke test.
4. **Regression**
   - All existing CLI watch tests keep passing untouched.
   - All existing web/modules tests keep passing; add migration test for new columns (additive, default values backfill).
5. **Doc tests**
   - `framekit service status` output schema is the same JSON used by Web UI dashboard card — snapshot test.

---

## 12. Explicitly Not Built Yet (out of scope)

To keep the first cut shippable:

- **Multi-host clustering / HA service.** Single host, single process. Not designed for two services sharing one config dir.
- **Per-user multi-tenancy.** Service runs as one OS user; auth gates Web UI access only.
- **Plugin sandboxing for intake-driven workflows.** Intake creates pipeline jobs with allowlisted modules only. No arbitrary Python execution path.
- **Push to external task systems** (Celery, RabbitMQ, Redis). Stay on SQLite as the queue.
- **Per-folder live filter editing UI.** `/api/v1/watch/rules` is sketched but UI lands later.
- **Web UI starts the service process directly.** Always defer to OS service manager; no privilege-escalation helper from inside FastAPI.
- **Encrypted-at-rest jobs DB.** SQLite jobs DB stays plain — it contains argv/stdout, no secrets if vault is used correctly.
- **Cross-machine intake auth (mTLS / OAuth).** Phase 1 = static per-source tokens; revisit later.
- **Auto-update / self-upgrade of the service.** User upgrades via `pip` then `framekit service restart`.
- **GUI tray / system notification daemon** beyond what `WindowsNotifier` already does inside watcher.
- **Replacing the existing per-request CLI subprocess execution with in-process import.** Subprocess is still the cleanest isolation boundary and lets us reuse all existing CLI code. Defer until profiling shows it matters.

---

### Inspection summary (read-only)

Files inspected (no modifications): [CLAUDE.md](CLAUDE.md), [AGENTS.md](AGENTS.md), [WEB_UI_V1_PLAN.md](WEB_UI_V1_PLAN.md), [paths.py](src/framekit/core/paths.py), [watch.py](src/framekit/commands/watch.py), [watch/service.py](src/framekit/modules/watch/service.py), [runs/ledger.py](src/framekit/core/runs/ledger.py), [webhooks.py](src/framekit/core/webhooks.py), [web/modules.py](src/framekit/web/modules.py) (relevant ranges), [web/app.py](src/framekit/web/app.py), [settings/store.py](src/framekit/core/settings/store.py), [auth/models.py](src/framekit/core/auth/models.py), [__main__.py](src/framekit/__main__.py). No code touched.