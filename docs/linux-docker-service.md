# Ouro — Linux and Docker Service Quick Start

Run Ouro as persistent background service on Linux via systemd user-unit,
or in Docker with packaged Web UI assets (no npm/runtime Node).

For full operations (backup/restore, intake token lifecycle, queue
drain/shutdown controls), see `docs/service-ops-runbook.md`.

---

## Linux (systemd user service)

Prerequisites:
- Linux with `systemd --user`
- `ouro` installed and on PATH

Migration note:
- Framekit-era unit/config paths are not migrated automatically.
- New user unit path is `~/.config/systemd/user/ouro.service`.
- Copy old local data manually if continuity is required.

Install user unit:

```bash
ouro service install --mode=systemd
```

Start / stop / restart:

```bash
ouro service start --mode=systemd
ouro service stop --mode=systemd
ouro service restart --mode=systemd
```

Status / logs:

```bash
ouro service status
ouro service logs -n 100
ouro service logs -f
```

Uninstall:

```bash
ouro service uninstall --mode=systemd
```

Unit path:

```text
~/.config/systemd/user/ouro.service
```

---

## Docker (single service)

Files:
- `Dockerfile`
- `docker-compose.service.yml`

Build image:

```bash
docker build -t ouro-service:local .
```

Auth note:
- `ouro serve --host 0.0.0.0` requires auth active.
- Create admin user once in persisted config volume before first `up`.

Bootstrap admin user:

```bash
docker compose -f docker-compose.service.yml run --rm ouro user add --admin
```

Why this works:
- Image entrypoint is `ouro`
- Default command is `serve --host 0.0.0.0 --port 8000`
- `docker compose run ... ouro user add --admin` overrides command with `user add --admin`
- Admin user is written into mounted config volume (`/var/lib/ouro/config`)

Run service:

```bash
docker compose -f docker-compose.service.yml up -d
```

Check:

```bash
docker compose -f docker-compose.service.yml ps
docker compose -f docker-compose.service.yml logs -f ouro
```

Default volumes:
- config: `/var/lib/ouro/config`
- cache: `/var/lib/ouro/cache`
- media: `/media` (bind from `./Workspace`)

Web UI:
- `http://127.0.0.1:8000`
- Static bundle served from packaged `ouro/web/static`.
