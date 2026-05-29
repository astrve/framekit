# Framekit Service Ops Runbook

Operational runbook for service lifecycle, first-admin bootstrap, intake token flow,
and backup/restore across Windows, Linux systemd user service, and Docker.

---

## 1) Build + package baseline

```cmd
npm run build
uv build --sdist --wheel
```

Why:
- Refresh packaged Web UI assets in `src/framekit/web/static`.
- Validate wheel/sdist include static bundle.

---

## 2) First admin bootstrap

### Local (Windows/Linux)

```cmd
framekit user add --admin
```

### Docker (before first `up` when binding `0.0.0.0`)

```bash
docker compose -f docker-compose.service.yml run --rm framekit user add --admin
```

Notes:
- `framekit serve --host 0.0.0.0` requires auth/admin guard satisfied.
- Admin record is persisted in mounted config volume.

---

## 3) Service lifecycle

### Windows

```cmd
framekit service install --mode=task
framekit service start
framekit service status
framekit service logs -f
framekit service stop
framekit service uninstall
```

### Linux (`systemd --user`)

```bash
framekit service install --mode=systemd
framekit service start --mode=systemd
framekit service status
framekit service logs -f
framekit service stop --mode=systemd
framekit service uninstall --mode=systemd
```

### Docker

```bash
docker compose -f docker-compose.service.yml up -d
docker compose -f docker-compose.service.yml ps
docker compose -f docker-compose.service.yml logs -f framekit
docker compose -f docker-compose.service.yml down
```

---

## 4) Health checks

```bash
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:8000/api/v1/service/status
curl -fsS http://127.0.0.1:8000/api/v1/events/recent?limit=20
```

Expected:
- `/healthz` => `{"status":"ok"}`
- service status returns PID/uptime/watcher/queue/metrics fields.

---

## 5) Queue controls (runtime)

```bash
# Snapshot
curl -fsS http://127.0.0.1:8000/api/v1/jobs/queue

# Drain on
curl -fsS -X POST http://127.0.0.1:8000/api/v1/service/drain -H "Content-Type: application/json" -d '{"enabled":true}'

# Drain off
curl -fsS -X POST http://127.0.0.1:8000/api/v1/service/drain -H "Content-Type: application/json" -d '{"enabled":false}'
```

Job controls:
- `POST /api/v1/jobs/{id}/priority`
- `POST /api/v1/jobs/{id}/pause`
- `POST /api/v1/jobs/{id}/resume`

Shutdown:
- `POST /api/v1/service/shutdown` (graceful request, process exits after running jobs drain or timeout).

---

## 6) Intake token lifecycle

Create source (token shown once):

```bash
curl -fsS -X POST http://127.0.0.1:8000/api/v1/intake/sources \
  -H "Content-Type: application/json" \
  -d '{"name":"qBittorrent","source_id":"qbittorrent-main","default_preset":"default"}'
```

Delete/revoke source:

```bash
curl -fsS -X DELETE http://127.0.0.1:8000/api/v1/intake/sources/qbittorrent-main
```

Submit intake release:

```bash
curl -fsS -X POST http://127.0.0.1:8000/api/v1/intake/release \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"source":"qbittorrent-main","path":"/media/My.Release"}'
```

---

## 7) Backup set

Backup these paths together:

- config root (`FRAMEKIT_CONFIG_DIR` or platform default):
  - `framekit.yaml`
  - `users.db`
  - `intake_sources.json`
  - `webhooks.json`
  - `service/` (includes `events.ndjson`, state, logs)
  - `runs/ledger.ndjson`
  - `security/vault.enc`
  - `security/master.key`
- cache root (`FRAMEKIT_CACHE_DIR` or platform default):
  - `web/module_jobs.sqlite3`

Notes:
- `vault.enc` + `master.key` must stay paired.
- Include `module_jobs.sqlite3` if queue continuity matters.

---

## 8) Restore procedure

1. Stop service.
2. Restore config root + cache root files to target machine.
3. Verify file permissions for `security/` and service directories.
4. Start service.
5. Check:
   - `/healthz`
   - `/api/v1/service/status`
   - `/api/v1/events/recent`
   - UI load at `/`

Expected after restore:
- Auth users preserved.
- Intake sources preserved.
- Vault-backed secrets usable.
- Queue and event history available (bounded by retention/rotation).

---

## 9) Known caveat

- Full `uv run pytest tests/ -q` may still be interrupted by external `KeyboardInterrupt` (`code 137`) in current runner.
- Use targeted test commands from `docs/codex-handoff.md` for stable validation.
