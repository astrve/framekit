# Ouro Service Mode — Current Status

Last updated after completing phases S1–S5, Web UI H1–H6, Intake UI, Service
Events/SSE with persisted history, queue controls, watch rules API, CI packaging
gate, and Retry/Resume Policy v1.

Migration note:
- Strict rename to Ouro: CLI is `ouro`.
- Package/project name is `ouro-auto`.
- Local config/cache/service paths now use `ouro` namespace.
- Old `framekit` local data is not auto-migrated or deleted.

---

## What is complete

### Web UI — Application-first UX (H1–H6)

| Batch | Work |
|---|---|
| H1 | Dashboard: live active-operations feed, recent-results table, status cards (doctor, upload, seedbox), warning banner |
| H2 | `InlineJobPanel` component: polls job API, live stdout, sub-step parsing, result summaries, cancel/rerun/debug |
| H3 | All module pages use `InlineJobPanel`; `DedicatedModuleLauncher` no longer navigates away; dry_run default on for destructive modules; destructive-confirm dialog |
| H4 | Pipeline, Batch, Upload, Seedbox pages use `InlineJobPanel`; inline result replaces standalone progress card |
| H5 | Jobs page cleaned up; "Configuration" title removed; pipeline/batch builders removed from jobs page |
| H6 | Settings moved to user menu; active profile chip; language picker wired |

Additional UI work completed:
- Rollback page (`/rollback`): ledger table, select run, inline job panel
- Intake page (`/intake`): source list/create/delete, one-time token reveal, copy action, security warning
- Inspect / Validate: structured result cards from `parsed_payload` JSON output
- Jobs canonical routes renamed to `/jobs` + `/jobs/:jobId` with legacy `/modules*` redirect
- Watch session wording corrections
- Full frontend build: `tsc -b && vite build` clean

### Service mode (S1–S5)

**S1 — `ouro serve` + durable service core**
- `ouro serve` command runs FastAPI + uvicorn in foreground or service mode
- Heartbeat thread writes `service.state.json` every 5 s
- `service.pid` written on start, removed on clean stop
- `service.lock` prevents duplicate instances
- DB-first SQLite job claiming: additive schema migration (priority, claimed_by, claimed_at, category, origin, request_hash, attempts, max_attempts, next_retry_at, last_failure_kind); claim-based worker loop replaces ThreadPoolExecutor
- Orphan recovery on restart: claimed rows whose worker is gone are re-enqueued or marked failed

**Retry / Resume Policy v1**
- Queue jobs support `attempts`, `max_attempts`, `next_retry_at`, `last_failure_kind`
- Pending jobs survive restart
- Running orphan jobs follow retry policy:
  - retryable transient failure path → back to pending with retry schedule
  - terminal path → failed with explicit failure kind
- Safe jobs auto-retry transient failures (`timeout`, `spawn_error`, `interrupted_restart`)
- Destructive apply-mode jobs are never auto-retried (manual rerun only)
- `retryable` is computed in API responses, not stored in DB
- Web UI shows retry metadata minimally (attempts/retry time/failure kind)

**Queue controls + drain/shutdown**
- `GET /api/v1/jobs/queue` returns pending/paused/running counts with per-category split
- `POST /api/v1/jobs/{id}/priority` updates pending job priority
- `POST /api/v1/jobs/{id}/pause` and `POST /api/v1/jobs/{id}/resume` control queue-level execution
- `POST /api/v1/service/drain` toggles drain mode (new jobs rejected while active)
- `POST /api/v1/service/shutdown` schedules graceful process shutdown after running jobs complete
- Claim query skips paused jobs and honors category concurrency limits from `settings.service.category_concurrency`

**S1c — Embedded watcher**
- `WatcherService` runs as a supervised in-process thread inside `ouro serve`
- File detection → job enqueue pipeline; no 7 200 s timeout workaround
- Watch folder reconciliation on settings reload
- Watch rules API added:
  - `GET /api/v1/watch/rules`
  - `POST /api/v1/watch/rules`
  - `PATCH /api/v1/watch/rules/{id}`
  - `DELETE /api/v1/watch/rules/{id}`
- Legacy `/api/v1/watch/folders` remains supported and maps to same storage

**S2 — Service status / reload / UI awareness**
- `GET /api/v1/service/status` returns mode, pid, uptime, subsystem states (watcher, worker, webhook, intake)
- `POST /api/v1/service/reload` reconciles watchers and workers from current settings without restart
- Dashboard service status card shows running/stopped, uptime, queue depth, last error
- Watch page reflects watcher subsystem state from service; start/stop wired to service control

**S3 — Intake API**
- `POST /api/v1/intake/release`: accepts release notification from external downloaders
- `GET/POST/DELETE /api/v1/intake/sources`: source CRUD (admin)
- Source tokens stored in vault under `intake.<source>.token`; never logged
- Dedup via `request_hash` (sha1 of source + path + dedup_key)
- Allowlisted roots via `settings.intake.allowed_roots`; path traversal blocked with `resolve()` + `is_relative_to()`
- Intake creates pipeline jobs only; no arbitrary command execution

**S4 — Windows service/task CLI**
- `ouro service install --mode=task|nssm|sc|auto`
- `ouro service start / stop / restart / status / logs / uninstall`
- `task` mode: bat wrapper with `>>` / `2>>` log redirection; CMD.EXE double-outer-quote convention for paths with spaces; no admin required (typically)
- `nssm` mode: restart-on-failure, log rotation (requires admin)
- `sc` mode: built-in fallback (requires admin, no log redirection)
- Heartbeat + PID file read locally in `service status`; 401 on API query is expected when auth is enabled

**S5 — Linux / Docker service support**
- `ouro service` supports Linux user service mode (`systemd --user`)
- Linux lifecycle commands wired: `install`, `uninstall`, `start`, `stop`, `restart`, `status`, `logs`
- User unit generated at `~/.config/systemd/user/ouro.service`
- Docker runtime added:
  - `Dockerfile` runs `ouro serve` directly
  - `docker-compose.service.yml` provides single-service example with config/cache/media volumes
  - No npm/Node required at runtime (packaged static assets served by Python package)

**Service events / SSE**
- In-process event bus/ring buffer implemented (`src/ouro/core/service/events.py`)
- Persisted history enabled: append-only `service/events.ndjson` with rotation
- `GET /api/v1/events/recent` implemented with limit validation
- `GET /api/v1/events/stream` implemented (`text/event-stream`, initial connected comment, keepalive ping, graceful disconnect)
- Lifecycle events emitted from service/job/watch/intake paths
- Web UI `/events` page consumes recent events + live SSE stream with degraded fallback state

### Production UI serving

- `npm run build` copies `web-ui/dist/` into `src/ouro/web/static/`
- Wheel/sdist include `ouro/web/static/index.html` and bundled assets
- `ouro serve` static resolution order:
  - packaged `ouro/web/static/`
  - source-tree `web-ui/dist/` fallback
  - fallback JSON hint if neither exists
- SPA catch-all `/{full_path:path}` serves static assets + falls back to `index.html`
- Path traversal protected: `resolve()` + `is_relative_to(static_root_resolved)`
- Auth middleware passes non-`/api/` requests through without token check
- `/api/*` remains reserved; SPA catch-all never swallows API routes

### Auth

- Infinite reload loop on `/login` fixed: `fetchValidated` 401 dispatches `ouro:unauthorized` DOM event instead of `window.location.href = "/login"`
- `AuthProvider` clears token + user from React state on event
- `AuthGuard` soft-navigates to `/login` via TanStack Router
- `AppShell.profilesQuery` disabled on `/login` — server never receives `/api/v1/profiles` from unauthenticated login page

### Developer tooling

- Root `package.json` now has `build`, `dev`, `typecheck` scripts proxied to `web-ui/`
- `npm run build` from repo root builds frontend and syncs static files into package path
- CI gating job added for service/web packaging:
  - `npm run build`
  - targeted service/web tests
  - `uv build --sdist --wheel`
  - wheel smoke install + `ouro serve` + `/healthz` + index check
- Pytest diagnostic CI job added (non-blocking): collect order + durations + tracemalloc subset

### Validation caveat (current runner)

- Full `uv run pytest tests/ -q` is interrupted by external `KeyboardInterrupt` (code 137)
- Targeted service/events/queue/watch/intake tests pass
- `npm run build` passes
- `uv build --sdist --wheel` passes

---

## Exact Windows commands to verify

```cmd
REM 1. Build UI (from repo root)
npm run build

REM 2. Foreground smoke test
uv run ouro serve
REM → open http://127.0.0.1:8000 — dashboard loads, no loop, Ctrl+C

REM 3. Install as scheduled task
ouro service install --mode=task

REM 4. Start and verify
ouro service start
ouro service status
ouro service logs -f

REM 5. Auth (optional — enables login)
ouro user add --admin
REM → open http://127.0.0.1:8000/login — form stable, no refresh loop

REM 6. Intake API (optional test)
REM   ouro intake source add --name qbit
REM   → use returned token as Bearer in:
REM   curl -X POST http://127.0.0.1:8000/api/v1/intake/release \
REM     -H "Authorization: Bearer <token>" \
REM     -d '{"source":"qbit","path":"C:\\media\\Movie.mkv"}'

REM 7. Clean up
ouro service stop
ouro service uninstall
```

Cross-platform operations runbook:
- `docs/service-ops-runbook.md`

---

## Known limitations

| Area | Detail |
|---|---|
| `task` mode | Logs appear only after first task run; no restart-on-failure |
| `nssm`/`sc` | Requires admin elevation |
| Linux systemd user service | Requires `systemd --user` session/tools (`systemctl`, `journalctl`) |
| Docker bind on `0.0.0.0` | Requires auth active (create admin first) due serve non-loopback guard |
| Token expiry | In-session expiry clears React state softly via DOM event; no toast shown to user |
| Job retry/resume follow-up | Attempt history table optional; intra-module resume not implemented; destructive retry policy remains manual-only |

---

## Risky areas — do not touch without careful review

| Area | Risk |
|---|---|
| `web-ui/src/lib/api/client.ts` 401 handler | DOM event approach just stabilized; test coverage limited |
| `src/ouro/web/app.py` auth middleware + catch-all route | Non-API passthrough and SPA catch-all order is precise; wrong order breaks API or auth |
| `src/ouro/core/service/windows.py` bat quoting | CMD.EXE double-outer-quote for paths with spaces is correct and subtle |
| SQLite claim semantics | `UPDATE … WHERE status='pending' LIMIT 1` + `RETURNING`; WAL mode; concurrent claimers need care |
| `tsconfig.app.json` strict flags | `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` intentional; do not relax |

---

## Recommended next work

### Priority order

1. **Attempt history table (optional)**
- Keep current job table and add separate attempt ledger only if deeper audit/debug is required.

2. **Intra-module resume (not implemented)**
- Current policy retries whole job attempts; no partial step resume yet.

3. **Destructive retry policy stays manual-only**
- Keep auto-retry disabled for destructive apply-mode jobs unless policy changes are explicitly approved.

4. **Runner stability (`code 137`)**
- Continue diagnosing external KeyboardInterrupt in full-suite runs; targeted suites are currently stable.

---

## Files to read before starting any of the above

| Task | Files |
|---|---|
| Global handoff | `docs/codex-handoff.md` |
| Linux/Docker service | `docs/linux-docker-service.md`, `src/ouro/core/service/linux.py`, `src/ouro/commands/service.py`, `Dockerfile`, `docker-compose.service.yml` |
| Queue controls / retry follow-up | `src/ouro/web/modules.py`, `src/ouro/web/app.py`, `tests/test_web_modules_runner.py` |
| Events persistence/history follow-up | `src/ouro/core/service/events.py`, `src/ouro/web/app.py`, `web-ui/src/routes/events.tsx` |
| Windows smoke/docs polish | `docs/windows-service.md`, `src/ouro/core/service/windows.py`, `src/ouro/commands/service.py` |
