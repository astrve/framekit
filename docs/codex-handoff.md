# Codex Handoff — Framekit

## Current completed state

### Web UI v1.0 (H1–H6)

All application-first UX batches are done.

- Dashboard has live job feed, recent results, status cards, and warning banner.
- Every module page uses `InlineJobPanel` for inline progress/result.
- The old “View Job” redirect-first flow was removed from main workflows.
- Pipeline, Batch, Upload, and Seedbox are wired.
- Jobs page is history/debug only.
- Settings nav includes active profile chip.
- Rollback page is functional.
- Inspect/Validate show structured result cards.
- Production build is clean: `tsc -b && vite build`.

### Service mode (S1–S5)

Implemented:

- `framekit serve`
  - FastAPI + uvicorn.
  - Resolves static UI from packaged `framekit/web/static/` first, then source-tree `web-ui/dist/` fallback.
  - Heartbeat + PID file.
  - Service lock.

- DB-first job queue
  - SQLite claim-based workers.
  - Orphan recovery on restart.
  - Additive schema fields:
    - `priority`
    - `claimed_by`
    - `claimed_at`
    - `category`
    - `origin`
    - `request_hash`
    - `attempts`

- Embedded watcher
  - `WatcherService` runs as a supervised thread inside `framekit serve`.
  - No more 7,200s web-job workaround for service mode.

- Service status/reload API
  - `GET /api/v1/service/status`
  - `POST /api/v1/service/reload`

- Service events / SSE
  - In-process event bus/ring buffer in `src/framekit/core/service/events.py`.
  - `GET /api/v1/events/recent` implemented.
  - `GET /api/v1/events/stream` implemented with initial comment, keepalive ping, and disconnect handling.
  - Events emitted from service/job/watch/intake lifecycle points.
  - Web UI `/events` page and nav entry wired for recent + live stream with degraded fallback.

- Intake API
  - `POST /api/v1/intake/release`
  - Source CRUD.
  - Vault token storage.
  - Dedup.
  - Allowlisted roots.

- Windows service CLI
  - `install`
  - `start`
  - `stop`
  - `restart`
  - `status`
  - `logs`
  - `uninstall`
  - Modes: `task`, `nssm`, `sc`, `auto`
  - Task mode uses a `.bat` wrapper with log capture.

- Linux service CLI
  - `install`
  - `start`
  - `stop`
  - `restart`
  - `status`
  - `logs`
  - `uninstall`
  - Mode: `systemd` (user unit), with `auto` resolving to `systemd` on Linux
  - Unit path: `~/.config/systemd/user/framekit.service`

- Docker service runtime
  - `Dockerfile` runs `framekit serve` directly (no npm runtime dependency)
  - `docker-compose.service.yml` provides single-service deployment with config/cache/media volumes
  - Packaged static assets served from Python package path inside container

### Auth

The infinite `/login` reload loop is fixed.

Current behavior:

- `fetchValidated` no longer does `window.location.href = "/login"` on 401.
- 401 dispatches a `framekit:unauthorized` DOM event.
- `AuthProvider` listens to the event and clears React auth state.
- `AuthGuard` soft-navigates to `/login`.
- `AppShell.profilesQuery` is disabled on `/login`.

### Tooling

Root npm scripts now proxy to `web-ui/`:

```cmd
npm run build
npm run dev
npm run typecheck
```

`npm run build` now builds Web UI, then copies `web-ui/dist/` into
`src/framekit/web/static/`.

### Packaged Web UI static assets

- `npm run build` copies `web-ui/dist/` into `src/framekit/web/static/`.
- `uv build --sdist --wheel` includes `framekit/web/static/index.html` and static assets.
- `framekit serve` resolves static in this order:
  - packaged `framekit/web/static/`
  - source-tree `web-ui/dist/`
  - fallback JSON hint if neither exists

### Test baseline

```cmd
uv run pytest tests/ -q
```

Current runner caveat:

- Full `uv run pytest tests/ -q` is interrupted by external `KeyboardInterrupt` (exit code 137) in current runner.
- Targeted static-serving tests pass.
- `npm run build` and `uv build --sdist --wheel` pass.

---

## Exact commands Codex should run first

```cmd
REM Orient and verify baseline
uv run pytest tests/ -q
npm run build
uv run framekit --version
uv run framekit serve --help
uv run framekit service --help
```

If any of those fail, stop and fix before coding anything.

```cmd
REM Verify production UI serving manually
uv run framekit serve
REM Open http://127.0.0.1:8000 in browser.
REM Dashboard/login should load.
REM Ctrl+C to stop.
```

```cmd
REM Verify service state dir
python -c "from framekit.core.paths import get_service_dir; print(get_service_dir())"
REM Expected on Windows:
REM C:\Users\<you>\AppData\Local\framekit\framekit\service
```

---

## Highest-priority next tasks

### Priority 1 — Intake UI

Backend endpoints already exist.

Potential UI:

- Intake sources list.
- Create source.
- Show token once.
- Revoke/delete source.
- Intake test/submit form.
- Recent intake requests if backend history exists or is added later.

Inspect before coding:

```text
web-ui/src/lib/api/endpoints.ts
web-ui/src/lib/api/schemas.ts
```

### Priority 2 — Job retry / resume policy

Goals:

- Wire `attempts` to concrete retry policy (`max_attempts`, backoff).
- Keep current queue semantics and failure visibility.

Inspect before coding:

```text
src/framekit/modules/batch/service.py
src/framekit/core/jobs/queue.py
```

### Priority 3 — Windows smoke checklist + docs polish

Goals:

- Add/refresh manual smoke checklist for `service install/start/status/logs/stop/uninstall`.
- Keep docs aligned with current task mode quoting and log behavior.

Inspect before coding:

```text
docs/windows-service.md
docs/service-mode-status.md
src/framekit/core/service/windows.py
```

### Priority 4 — Linux service hardening

Goals:

- Expand `systemd --user` smoke coverage across distro variants.
- Improve fallback UX when `systemd --user` tools are missing.
- Improve Docker auth/bootstrap ergonomics.

Inspect before coding:

```text
docs/linux-docker-service.md
src/framekit/core/service/linux.py
src/framekit/commands/service.py
Dockerfile
docker-compose.service.yml
```

### Priority 5 — Events persistence/history (optional)

Goals:

- Keep current SSE API shape and live behavior unchanged.
- Add persisted history only if product needs retention beyond in-memory ring buffer.

---

## Files Codex must inspect before coding

### Always read first

```text
CLAUDE.md
AGENTS.md
docs/service-mode-status.md
docs/windows-service.md
SERVICE_MODE_PLAN.md
WEB_UI_V1_PLAN.md
```

### Before Web UI work

```text
web-ui/src/lib/api/endpoints.ts
web-ui/src/lib/api/schemas.ts
web-ui/src/lib/api/client.ts
web-ui/src/lib/auth.tsx
web-ui/src/routes/root.tsx
web-ui/src/components/layout/app-shell.tsx
```

### Before service/backend work

```text
SERVICE_MODE_PLAN.md
src/framekit/web/app.py
src/framekit/web/modules.py
src/framekit/core/service/windows.py
src/framekit/commands/service.py
```

---

## Known traps — do not redo or accidentally break these

### 1. `client.ts` 401 handler

Old behavior:

```ts
window.location.href = "/login"
```

Do not restore that.

Current behavior:

- Dispatch `new CustomEvent("framekit:unauthorized")`.
- Listener is in `auth.tsx`.
- Preserves SPA behavior and prevents login loops.

### 2. `app.py` middleware + SPA route order

Important current behavior:

- Non-API paths bypass auth middleware.
- API paths remain protected.
- SPA catch-all route is registered last.
- Catch-all must not swallow `/api/*`.

Changing route order can break API routing or auth.

### 3. `windows.py` CMD.EXE quoting

`_build_task_tr(bat_path)` uses double-outer-quote for paths with spaces:

```text
cmd.exe /c ""E:\path with spaces\framekit-serve.bat""
```

This is intentional. Do not simplify it.

### 4. TypeScript strict flags

These are intentional:

```json
"noUncheckedIndexedAccess": true,
"exactOptionalPropertyTypes": true
```

Do not relax them.

Implications:

- Test fixtures for `ModuleJob` need `priority: 0`.
- Array index access often needs `!` or a guard.
- Optional props must not pass `undefined` unless the type allows it.

### 5. Use `npm run build`, not `npx tsc --noEmit`

The root `tsconfig.json` has `"files": []`, so `npx tsc --noEmit` can be misleading.

Use:

```cmd
npm run build
```

This runs:

```cmd
tsc -b && vite build
```

### 6. Zod v4 `z.record`

Zod v4 requires two args:

```ts
z.record(z.string(), valueSchema)
```

Do not use:

```ts
z.record(z.string())
```

### 7. TanStack Query v5 mutation signatures

`mutationFn` receives a single variables object/value.

Multi-argument functions need wrapping:

```ts
mutationFn: (name: string) => useSeedbox(name)
```

### 8. `window.location.href = "/"` in `login.tsx`

This hard reload after successful login is currently intentional.

Do not replace with soft navigation unless you verify `AuthProvider` reinitializes correctly.

### 9. Python baseline

Run after Python changes:

```cmd
uv run pytest tests/ -q
```

Expected baseline:

```text
1959 passed, 16 skipped
```

### 10. S1–S4 are done

Do not restart or re-implement:

- S1 service core
- S1b DB-first queue
- S1c embedded watcher
- S2 service status/reload/UI awareness
- S3 intake API
- S4 Windows service/task CLI
