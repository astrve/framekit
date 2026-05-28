# Framekit — Linux and Docker Service Quick Start

Run Framekit as persistent background service on Linux via systemd user-unit,
or in Docker with packaged Web UI assets (no npm/runtime Node).

---

## Linux (systemd user service)

Prerequisites:
- Linux with `systemd --user`
- `framekit` installed and on PATH

Install user unit:

```bash
framekit service install --mode=systemd
```

Start / stop / restart:

```bash
framekit service start --mode=systemd
framekit service stop --mode=systemd
framekit service restart --mode=systemd
```

Status / logs:

```bash
framekit service status
framekit service logs -n 100
framekit service logs -f
```

Uninstall:

```bash
framekit service uninstall --mode=systemd
```

Unit path:

```text
~/.config/systemd/user/framekit.service
```

---

## Docker (single service)

Files:
- `Dockerfile`
- `docker-compose.service.yml`

Build image:

```bash
docker build -t framekit-service:local .
```

Auth note:
- `framekit serve --host 0.0.0.0` requires auth active.
- Create admin user once in persisted config volume before first `up`.

Bootstrap admin user:

```bash
docker compose -f docker-compose.service.yml run --rm framekit user add --admin
```

Why this works:
- Image entrypoint is `framekit`
- Default command is `serve --host 0.0.0.0 --port 8000`
- `docker compose run ... framekit user add --admin` overrides command with `user add --admin`
- Admin user is written into mounted config volume (`/var/lib/framekit/config`)

Run service:

```bash
docker compose -f docker-compose.service.yml up -d
```

Check:

```bash
docker compose -f docker-compose.service.yml ps
docker compose -f docker-compose.service.yml logs -f framekit
```

Default volumes:
- config: `/var/lib/framekit/config`
- cache: `/var/lib/framekit/cache`
- media: `/media` (bind from `./Workspace`)

Web UI:
- `http://127.0.0.1:8000`
- Static bundle served from packaged `framekit/web/static`.
