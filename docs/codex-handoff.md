# Codex Handoff — Ouro

Migration note:
- Rename is strict: CLI command is `ouro` only.
- Package/project name is `ouro-auto`.
- Config/cache/service defaults now use `ouro` paths.
- No automatic deletion/move of old `framekit` local data.

## Current completed state

### Web UI v1.0 (H1–H6)

Done:
- Dashboard live feed, status cards, warnings.
- `InlineJobPanel` across workflows/modules.
- Pipeline/Batch/Upload/Seedbox inline execution.
- Jobs page = history/debug surface.
- Settings in user menu + active profile chip + language picker.
- Rollback page working.
- Intake page working (list/create/delete source, one-time token display).
- Events page working (recent + SSE live/degraded mode).
- Jobs canonical routes renamed to `/jobs` + `/jobs/:jobId`.
- Legacy `/modules*` routes kept via redirect.

### Service mode (S1–S5)

Done:
- `ouro serve` with lock/PID/heartbeat.
- Packaged static first (`ouro/web/static`), source fallback second (`web-ui/dist`).
- DB-first queue, orphan recovery, Retry/Resume v1.
- Queue fields: `attempts`, `max_attempts`, `next_retry_at`, `last_failure_kind`.
- Embedded watcher supervision.
- Service status/reload API.
- Intake API + source CRUD + vault token + dedup + root allowlist.
- Windows service/task CLI.
- Linux systemd user service CLI.
- Docker runtime (`Dockerfile`, `docker-compose.service.yml`).

### Service events / history / queue controls

Done:
- SSE endpoints:
  - `GET /api/v1/events/recent`
  - `GET /api/v1/events/stream`
- Events persisted in `service/events.ndjson` (rotating history).
- Service status now includes queue snapshot + metrics counters.
- New service controls:
  - `POST /api/v1/service/drain`
  - `POST /api/v1/service/shutdown`
- New queue controls:
  - `GET /api/v1/jobs/queue`
  - `POST /api/v1/jobs/{id}/priority`
  - `POST /api/v1/jobs/{id}/pause`
  - `POST /api/v1/jobs/{id}/resume`
- Claim logic skips paused jobs and respects category caps.

### Watch rules API

Done:
- `GET /api/v1/watch/rules`
- `POST /api/v1/watch/rules`
- `PATCH /api/v1/watch/rules/{id}`
- `DELETE /api/v1/watch/rules/{id}`
- Legacy `/api/v1/watch/folders` kept compatible.

### CI and packaging gate

Done:
- CI service/web gate:
  - `npm run build`
  - targeted service/web tests
  - `uv build --sdist --wheel`
  - wheel smoke install + `ouro serve` + `/healthz` + index check
- Pytest diagnostic CI job (non-blocking): collect order, durations, tracemalloc subset.

---

## Validation baseline

Primary checks:

```cmd
uv run pytest tests/test_web_modules_runner.py -q
uv run pytest tests/test_service_events.py -q
uv run pytest tests/test_web_api.py -q -k "events_recent or events_stream or service or jobs or watch or intake"
npm run build
uv build --sdist --wheel
```

Runner caveat:
- Full `uv run pytest tests/ -q` still intermittently interrupted by external `KeyboardInterrupt` (`code 137`).
- Targeted suites above pass.

---

## Exact commands Codex should run first

```cmd
uv run ouro --version
uv run ouro serve --help
uv run ouro service --help
npm run build
uv build --sdist --wheel
```

Optional wheel smoke (isolated config dir):

```cmd
set OURO_CONFIG_DIR=%CD%\.smoke-config
set OURO_CONFIG=%CD%\.smoke-config\ouro.yaml
uv run ouro serve --host 127.0.0.1 --port 8765
```

---

## Highest-priority next tasks

1. Attempt history table (optional, separate from v1 queue row fields).
2. Intra-module resume (not implemented; current retries are whole-attempt).
3. Keep destructive apply-mode retries manual-only unless explicit policy change.
4. Continue root-cause investigation for full-suite `code 137` interruptions.

---

## Files Codex must inspect before coding

Always:

```text
CLAUDE.md
AGENTS.md
docs/service-mode-status.md
docs/windows-service.md
SERVICE_MODE_PLAN.md
WEB_UI_V1_PLAN.md
```

Queue/service follow-up:

```text
src/ouro/web/modules.py
src/ouro/web/app.py
src/ouro/core/service/events.py
tests/test_web_modules_runner.py
tests/test_web_api.py
```

Linux/Docker/service operations:

```text
docs/linux-docker-service.md
docs/service-ops-runbook.md
src/ouro/core/service/linux.py
src/ouro/commands/service.py
Dockerfile
docker-compose.service.yml
```
