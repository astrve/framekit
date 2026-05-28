# Framekit Service Mode — Current Status

Last updated after completing phases S1–S5, production UI serving, packaged
Web UI static assets, Web UI v1.0 application-first UX (H1–H6), and auth loop fix.

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
| H6 | Settings accessible from nav; active profile chip; language picker wired |

Additional UI work completed:
- Rollback page (`/rollback`): ledger table, select run, inline job panel
- Inspect / Validate: structured result cards from `parsed_payload` JSON output
- Watch session wording corrections
- Full frontend build: `tsc -b && vite build` clean

### Service mode (S1–S5)

**S1 — `framekit serve` + durable service core**
- `framekit serve` command runs FastAPI + uvicorn in foreground or service mode
- Heartbeat thread writes `service.state.json` every 5 s
- `service.pid` written on start, removed on clean stop
- `service.lock` prevents duplicate instances
- DB-first SQLite job claiming: additive schema migration (priority, claimed_by, claimed_at, category, origin, request_hash, attempts); claim-based worker loop replaces ThreadPoolExecutor
- Orphan recovery on restart: claimed rows whose worker is gone are re-enqueued or marked failed

**S1c — Embedded watcher**
- `WatcherService` runs as a supervised in-process thread inside `framekit serve`
- File detection → job enqueue pipeline; no 7 200 s timeout workaround
- Watch folder reconciliation on settings reload

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
- `framekit service install --mode=task|nssm|sc|auto`
- `framekit service start / stop / restart / status / logs / uninstall`
- `task` mode: bat wrapper with `>>` / `2>>` log redirection; CMD.EXE double-outer-quote convention for paths with spaces; no admin required (typically)
- `nssm` mode: restart-on-failure, log rotation (requires admin)
- `sc` mode: built-in fallback (requires admin, no log redirection)
- Heartbeat + PID file read locally in `service status`; 401 on API query is expected when auth is enabled

**S5 — Linux / Docker service support**
- `framekit service` supports Linux user service mode (`systemd --user`)
- Linux lifecycle commands wired: `install`, `uninstall`, `start`, `stop`, `restart`, `status`, `logs`
- User unit generated at `~/.config/systemd/user/framekit.service`
- Docker runtime added:
  - `Dockerfile` runs `framekit serve` directly
  - `docker-compose.service.yml` provides single-service example with config/cache/media volumes
  - No npm/Node required at runtime (packaged static assets served by Python package)

**Service events / SSE**
- In-process event bus/ring buffer implemented (`src/framekit/core/service/events.py`)
- `GET /api/v1/events/recent` implemented with limit validation
- `GET /api/v1/events/stream` implemented (`text/event-stream`, initial connected comment, keepalive ping, graceful disconnect)
- Lifecycle events emitted from service/job/watch/intake paths
- Web UI `/events` page consumes recent events + live SSE stream with degraded fallback state

### Production UI serving

- `npm run build` copies `web-ui/dist/` into `src/framekit/web/static/`
- Wheel/sdist include `framekit/web/static/index.html` and bundled assets
- `framekit serve` static resolution order:
  - packaged `framekit/web/static/`
  - source-tree `web-ui/dist/` fallback
  - fallback JSON hint if neither exists
- SPA catch-all `/{full_path:path}` serves static assets + falls back to `index.html`
- Path traversal protected: `resolve()` + `is_relative_to(static_root_resolved)`
- Auth middleware passes non-`/api/` requests through without token check
- `/api/*` remains reserved; SPA catch-all never swallows API routes

### Auth

- Infinite reload loop on `/login` fixed: `fetchValidated` 401 dispatches `framekit:unauthorized` DOM event instead of `window.location.href = "/login"`
- `AuthProvider` clears token + user from React state on event
- `AuthGuard` soft-navigates to `/login` via TanStack Router
- `AppShell.profilesQuery` disabled on `/login` — server never receives `/api/v1/profiles` from unauthenticated login page

### Developer tooling

- Root `package.json` now has `build`, `dev`, `typecheck` scripts proxied to `web-ui/`
- `npm run build` from repo root builds frontend and syncs static files into package path

### Validation caveat (current runner)

- Full `uv run pytest tests/ -q` is interrupted by external `KeyboardInterrupt` (code 137)
- Targeted static-serving tests pass
- `npm run build` passes
- `uv build --sdist --wheel` passes

---

## Exact Windows commands to verify

```cmd
REM 1. Build UI (from repo root)
npm run build

REM 2. Foreground smoke test
uv run framekit serve
REM → open http://127.0.0.1:8000 — dashboard loads, no loop, Ctrl+C

REM 3. Install as scheduled task
framekit service install --mode=task

REM 4. Start and verify
framekit service start
framekit service status
framekit service logs -f

REM 5. Auth (optional — enables login)
framekit user add --admin
REM → open http://127.0.0.1:8000/login — form stable, no refresh loop

REM 6. Intake API (optional test)
REM   framekit intake source add --name qbit
REM   → use returned token as Bearer in:
REM   curl -X POST http://127.0.0.1:8000/api/v1/intake/release \
REM     -H "Authorization: Bearer <token>" \
REM     -d '{"source":"qbit","path":"C:\\media\\Movie.mkv"}'

REM 7. Clean up
framekit service stop
framekit service uninstall
```

---

## Known limitations

| Area | Detail |
|---|---|
| `task` mode | Logs appear only after first task run; no restart-on-failure |
| `nssm`/`sc` | Requires admin elevation |
| Linux systemd user service | Requires `systemd --user` session/tools (`systemctl`, `journalctl`) |
| Docker bind on `0.0.0.0` | Requires auth active (create admin first) due serve non-loopback guard |
| Token expiry | In-session expiry clears React state softly via DOM event; no toast shown to user |
| Intake UI | No management page for intake sources in Web UI (API exists, UI not yet built) |
| Service events/SSE | In-memory ring buffer only; no persisted event history yet |
| Job retry/resume | `attempts` column in DB; retry policy (max attempts, backoff) not yet wired |

---

## Risky areas — do not touch without careful review

| Area | Risk |
|---|---|
| `web-ui/src/lib/api/client.ts` 401 handler | DOM event approach just stabilized; test coverage limited |
| `src/framekit/web/app.py` auth middleware + catch-all route | Non-API passthrough and SPA catch-all order is precise; wrong order breaks API or auth |
| `src/framekit/core/service/windows.py` bat quoting | CMD.EXE double-outer-quote for paths with spaces is correct and subtle |
| SQLite claim semantics | `UPDATE … WHERE status='pending' LIMIT 1` + `RETURNING`; WAL mode; concurrent claimers need care |
| `tsconfig.app.json` strict flags | `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` intentional; do not relax |

---

## Recommended next work

### Priority order

1. **Intake UI**
- Source list page: create source (token shown once), revoke, toggle enabled
- Intake history table (accepted/rejected, dedup_hit flag)
- No new backend endpoints needed — all exist under `/api/v1/intake/`

2. **Job retry / resume policy**
`attempts` column already in DB. Add `max_attempts` setting and per-category
backoff in the worker loop.

3. **Windows smoke checklist / docs polish**
- Refresh checklist: install, start, status, logs, stop, uninstall
- Keep docs aligned with current task-mode quoting and logging behavior

4. **Linux service hardening**
- Broader smoke checklist for `systemctl --user` lifecycle on multiple distros
- Optional fallback UX when `systemd --user` unavailable
- Container auth/bootstrap ergonomics improvements

5. **Events persistence/history (optional)**
- Keep current SSE contract; add persistence only if history requirements grow
- Candidate scope: append-only event log + bounded history API

---

## Files to read before starting any of the above

| Task | Files |
|---|---|
| Global handoff | `docs/codex-handoff.md` |
| Linux/Docker service | `docs/linux-docker-service.md`, `src/framekit/core/service/linux.py`, `src/framekit/commands/service.py`, `Dockerfile`, `docker-compose.service.yml` |
| Intake UI | `web-ui/src/lib/api/endpoints.ts` (intake fns), `web-ui/src/lib/api/schemas.ts` (`IntakeSource*`) |
| Events persistence/history (optional) | `SERVICE_MODE_PLAN.md` §8.5, `src/framekit/core/service/events.py`, `src/framekit/web/app.py`, `web-ui/src/routes/events.tsx` |
| Retry/resume policy | `src/framekit/modules/batch/service.py`, `src/framekit/core/jobs/queue.py` |
| Windows smoke/docs polish | `docs/windows-service.md`, `src/framekit/core/service/windows.py`, `src/framekit/commands/service.py` |
