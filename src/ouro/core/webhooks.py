"""Webhook dispatch for Ouro events.

Stores webhook configs in config/webhooks.json.
Dispatches HTTP POST (fire-and-forget) on job/watch events.
Discord webhooks use embed format; generic webhooks use plain JSON.
"""

from __future__ import annotations

import json
import string
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from loguru import logger

from ouro.core.paths import get_config_dir


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

SUPPORTED_EVENTS = frozenset(
    {
        "job.started",
        "job.completed",
        "job.failed",
        "watch.file_detected",
    }
)

DISCORD_COLORS = {
    "job.started": 0x3A6EA8,       # blue
    "job.completed": 0x4A8C5C,     # green
    "job.failed": 0xB04040,        # red
    "watch.file_detected": 0xB07040,  # amber
}

ALLOWED_PLACEHOLDERS = frozenset(
    {"event", "module", "args", "path", "returncode", "error", "timestamp", "job_id"}
)


def _validate_template(template: str) -> None:
    """Raise ValueError if template contains unknown placeholders or invalid syntax."""
    try:
        parts = list(string.Formatter().parse(template))
    except ValueError as exc:
        raise ValueError(f"Invalid template syntax: {exc}") from exc
    for _, field_name, _, _ in parts:
        if field_name is not None:
            name = field_name.split(".")[0].split("[")[0]
            if name and name not in ALLOWED_PLACEHOLDERS:
                allowed = ", ".join(f"{{{p}}}" for p in sorted(ALLOWED_PLACEHOLDERS))
                raise ValueError(f"Unknown placeholder: {{{name}}}. Allowed: {allowed}")


def _render_template(template: str, context: dict[str, str]) -> str:
    """Render a validated template. Unknown keys render as empty string."""
    safe = {k: context.get(k, "") for k in ALLOWED_PLACEHOLDERS}
    return template.format_map(safe)


@dataclass
class WebhookConfig:
    """One registered webhook endpoint."""

    id: str
    name: str
    url: str
    enabled: bool = True
    discord: bool = False
    events: list[str] = field(default_factory=lambda: list(SUPPORTED_EVENTS))
    title_template: str | None = None
    body_template: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WebhookConfig:
        """Deserialize from plain dict."""
        return cls(
            id=str(data.get("id", uuid4())),
            name=str(data.get("name", "")),
            url=str(data.get("url", "")),
            enabled=bool(data.get("enabled", True)),
            discord=bool(data.get("discord", False)),
            events=[str(e) for e in data.get("events", list(SUPPORTED_EVENTS))],
            # Absent or empty string → None (treat as unset)
            title_template=data.get("title_template") or None,
            body_template=data.get("body_template") or None,
        )


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

_WEBHOOKS_LOCK = threading.Lock()


def _webhooks_path() -> Path:
    return get_config_dir() / "webhooks.json"


def load_webhooks() -> list[WebhookConfig]:
    """Load all webhook configs from disk."""
    path = _webhooks_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        return [WebhookConfig.from_dict(item) for item in raw if isinstance(item, dict)]
    except Exception as exc:
        logger.warning("Failed to load webhooks: {}", exc)
        return []


def save_webhooks(webhooks: list[WebhookConfig]) -> None:
    """Persist webhook configs to disk."""
    path = _webhooks_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _WEBHOOKS_LOCK:
        path.write_text(
            json.dumps([w.to_dict() for w in webhooks], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def add_webhook(
    *,
    name: str,
    url: str,
    discord: bool = False,
    events: list[str] | None = None,
    title_template: str | None = None,
    body_template: str | None = None,
) -> list[WebhookConfig]:
    """Add one webhook and return the updated list."""
    name = name.strip()
    url = url.strip()
    if not name:
        raise ValueError("webhook name is required")
    if not url.startswith(("http://", "https://")):
        raise ValueError("webhook URL must start with http:// or https://")
    chosen_events = [e for e in (events or list(SUPPORTED_EVENTS)) if e in SUPPORTED_EVENTS]
    if not chosen_events:
        chosen_events = list(SUPPORTED_EVENTS)
    # Normalize and validate templates
    title_template = title_template.strip() if title_template and title_template.strip() else None
    body_template = body_template.strip() if body_template and body_template.strip() else None
    if title_template:
        _validate_template(title_template)
    if body_template:
        _validate_template(body_template)
    webhooks = load_webhooks()
    webhooks.append(
        WebhookConfig(
            id=str(uuid4()),
            name=name,
            url=url,
            enabled=True,
            discord=discord,
            events=chosen_events,
            title_template=title_template,
            body_template=body_template,
        )
    )
    save_webhooks(webhooks)
    return webhooks


def remove_webhook(webhook_id: str) -> list[WebhookConfig]:
    """Remove one webhook by ID and return the updated list."""
    webhooks = [w for w in load_webhooks() if w.id != webhook_id]
    save_webhooks(webhooks)
    return webhooks


def update_webhook(
    webhook_id: str,
    *,
    enabled: bool | None = None,
    name: str | None = None,
    url: str | None = None,
    discord: bool | None = None,
    events: list[str] | None = None,
    title_template: str | None = None,
    body_template: str | None = None,
) -> list[WebhookConfig]:
    """Update one webhook's fields. Only provided (non-None) fields are changed.

    For title_template / body_template:
        None    = don't change
        ""      = clear (set to None / use default)
        str     = set to new value (validated)
    """
    if url is not None:
        url = url.strip()
        if url and not url.startswith(("http://", "https://")):
            raise ValueError("webhook URL must start with http:// or https://")
    # Validate templates before touching disk
    _tt = title_template.strip() if title_template is not None else None
    _bt = body_template.strip() if body_template is not None else None
    if _tt:
        _validate_template(_tt)
    if _bt:
        _validate_template(_bt)
    webhooks = load_webhooks()
    for wh in webhooks:
        if wh.id == webhook_id:
            if enabled is not None:
                wh.enabled = enabled
            if name is not None:
                wh.name = name.strip()
            if url is not None:
                wh.url = url
            if discord is not None:
                wh.discord = discord
            if events is not None:
                wh.events = [e for e in events if e in SUPPORTED_EVENTS] or list(SUPPORTED_EVENTS)
            if title_template is not None:   # "" → clear, non-empty → set
                wh.title_template = _tt or None
            if body_template is not None:
                wh.body_template = _bt or None
    save_webhooks(webhooks)
    return webhooks


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _build_discord_payload(
    event: str,
    data: dict[str, Any],
    *,
    title_template: str | None = None,
    body_template: str | None = None,
) -> dict[str, Any]:
    """Build a Discord webhook embed payload."""
    color = DISCORD_COLORS.get(event, 0x808080)
    now = datetime.now(UTC).isoformat()

    context: dict[str, str] = {
        "event": event,
        "module": str(data.get("module", "")),
        "args": str(data.get("args_text", "")),
        "path": str(data.get("path", "")),
        "returncode": str(data.get("returncode", "")) if data.get("returncode") is not None else "",
        "error": str(data.get("error", "")),
        "timestamp": now,
        "job_id": str(data.get("job_id", "")),
    }

    # Title
    if title_template:
        embed_title = _render_template(title_template, context)
    else:
        embed_title = f"Ouro — {event.replace('.', ' ').title()}"

    # Description/body
    if body_template:
        description = _render_template(body_template, context)
    else:
        description_parts: list[str] = []
        if event.startswith("job."):
            module = context["module"]
            args = context["args"]
            cmd = f"`ouro {module}{' ' + args if args else ''}`"
            description_parts.append(cmd)
            if data.get("error"):
                description_parts.append(f"Error: {data['error']}")
            rc = data.get("returncode")
            if rc is not None and rc != 0:
                description_parts.append(f"Exit code: {rc}")
        elif event == "watch.file_detected":
            description_parts.append(f"File: `{context['path']}`")
        description = "\n".join(description_parts) or event

    return {
        "embeds": [
            {
                "title": embed_title,
                "description": description,
                "color": color,
                "timestamp": now,
                "footer": {"text": "Ouro"},
            }
        ]
    }


def _build_generic_payload(event: str, data: dict[str, Any]) -> dict[str, Any]:
    """Build a generic JSON webhook payload."""
    return {
        "event": event,
        "timestamp": datetime.now(UTC).isoformat(),
        "source": "ouro",
        "data": data,
    }


def _post_webhook(webhook: WebhookConfig, payload: dict[str, Any]) -> None:
    """Send one webhook HTTP POST (called in a daemon thread)."""
    try:
        import httpx

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                webhook.url,
                json=payload,
                headers={"Content-Type": "application/json", "User-Agent": "Ouro/2.0"},
            )
            if response.status_code >= 400:
                logger.warning(
                    "Webhook '{}' returned HTTP {}: {}",
                    webhook.name,
                    response.status_code,
                    response.text[:200],
                )
    except Exception as exc:
        logger.warning("Webhook '{}' dispatch failed: {}", webhook.name, exc)


def dispatch_webhook_event(event: str, data: dict[str, Any] | None = None) -> None:
    """Fire-and-forget dispatch of a webhook event to all enabled subscribers.

    Args:
        event: One of SUPPORTED_EVENTS (e.g. ``"job.completed"``)
        data: Arbitrary event data dict passed to payload builders
    """
    if event not in SUPPORTED_EVENTS:
        return

    data = data or {}

    try:
        webhooks = load_webhooks()
    except Exception:
        return

    for wh in webhooks:
        if not wh.enabled:
            continue
        if event not in wh.events:
            continue
        payload = (
            _build_discord_payload(
                event, data,
                title_template=wh.title_template,
                body_template=wh.body_template,
            )
            if wh.discord
            else _build_generic_payload(event, data)
        )
        thread = threading.Thread(target=_post_webhook, args=(wh, payload), daemon=True)
        thread.start()


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "SUPPORTED_EVENTS",
    "WebhookConfig",
    "add_webhook",
    "dispatch_webhook_event",
    "load_webhooks",
    "remove_webhook",
    "update_webhook",
]
