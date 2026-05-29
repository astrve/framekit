# Framekit — Windows Service Quick Start

Run Framekit as a persistent background process on Windows so the Web UI
is available after login without keeping a terminal open.

For full cross-platform operations (backup/restore, intake token lifecycle,
drain/shutdown queue controls), see `docs/service-ops-runbook.md`.

---

## 1. Prerequisites

- Framekit installed (`uv pip install -e .` or equivalent)
- `framekit` available on PATH (verify: `framekit --version`)
- Web UI built (see step 2)

---

## 2. Build the Web UI

Run once, and again after any frontend update:

```cmd
npm run build
```

This builds `web-ui/dist/` then syncs static assets into
`src/framekit/web/static/`. `framekit serve` resolves packaged static first,
then source-tree fallback.

For Linux/Docker service setup, see `docs/linux-docker-service.md`.

---

## 3. Test in the foreground first

Before installing as a service, confirm the server starts cleanly:

```cmd
uv run framekit serve
```

Expected output:

```
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Open `http://127.0.0.1:8000` in a browser. The Framekit dashboard should
load. Press `Ctrl+C` to stop.

---

## 4. Install as a scheduled task

The `task` mode registers a Windows Scheduled Task that starts Framekit
automatically when you log in. It typically does **not** require admin
rights, though an elevated shell or restrictive group policy may block it.

```cmd
framekit service install --mode=task
```

Other install modes (require admin):

| Mode   | Description                                     |
|--------|-------------------------------------------------|
| `task` | Scheduled task, ONLOGON trigger (recommended)   |
| `nssm` | NSSM Windows service — best log support         |
| `sc`   | Built-in `sc.exe` service — no log redirection  |
| `auto` | Tries nssm → sc → task automatically            |

Custom host/port:

```cmd
framekit service install --mode=task --host 127.0.0.1 --port 8000
```

---

## 5. Start, status, logs, stop, uninstall

**Start** (triggers the scheduled task or service immediately):

```cmd
framekit service start
```

**Status** (reads the service heartbeat file and queries the API):

```cmd
framekit service status
```

> **Note on 401 in status output:** If auth is enabled (you have created at
> least one user with `framekit user add --admin`), `service status` queries
> `GET /api/v1/service/status` without credentials and may show a 401
> warning alongside the process/heartbeat data. The service is running
> normally — the 401 just means the status API endpoint requires login.
> The heartbeat file and PID are read locally and are always accurate.

**Tail logs** (stdout):

```cmd
framekit service logs -f
```

**Show last 100 lines of stderr**:

```cmd
framekit service logs --stderr -n 100
```

**Stop**:

```cmd
framekit service stop
```

**Restart** (stop then start):

```cmd
framekit service restart
```

**Uninstall** (removes the task/service entry; does not delete logs):

```cmd
framekit service uninstall
```

---

## 6. Where files are stored

All service state lives under the platform config directory:

```
%LOCALAPPDATA%\framekit\framekit\service\
```

Typical path: `C:\Users\<you>\AppData\Local\framekit\framekit\service\`

| File                     | Purpose                                      |
|--------------------------|----------------------------------------------|
| `service.pid`            | PID of the running server process            |
| `service.state.json`     | Heartbeat snapshot (status, uptime, etc.)    |
| `framekit-serve.bat`     | Wrapper script used by the scheduled task    |
| `framekit-serve.out.log` | stdout log (written by the bat wrapper)      |
| `framekit-serve.err.log` | stderr log (written by the bat wrapper)      |

> **Log note:** In `task` mode, logs are only written after the first task
> run. If `framekit service logs` shows no output immediately after install,
> start the service (`framekit service start`) and wait a few seconds.

---

## 7. Known limitations

- **Task mode logs**: the bat wrapper captures stdout/stderr to log files.
  The logs appear only after the task has run at least once.
- **Non-loopback binding**: `framekit serve` refuses `--host 0.0.0.0`
  unless at least one admin user exists (`framekit user add --admin`).
  Create the user before installing the service if you need LAN access.
- **Web UI must be built**: `framekit serve` serves `web-ui/dist/`. If the
  packaged static directory is missing, `framekit serve` falls back to
  source-tree `web-ui/dist/`; if neither exists, root returns JSON hint
  instead of UI. Re-run `npm run build` after frontend changes.
- **Token expiry**: JWT tokens expire. Users will be redirected to `/login`
  when their session expires; no data is lost.
- **No auto-restart for `task` mode**: the scheduled task runs on login but
  does not restart if the process crashes. Use `nssm` mode for
  restart-on-failure behaviour (requires admin).
- **Single host**: the service is designed for single-machine use. Running
  two Framekit instances pointing at the same config directory is not
  supported.

---

## 8. Upgrading

1. Stop the service: `framekit service stop`
2. Upgrade Framekit: `uv pip install --upgrade framekit` (or `uv sync`)
3. Rebuild the Web UI: `npm run build`
4. Start the service: `framekit service start`

No re-install is needed unless the CLI entry point path changes.
