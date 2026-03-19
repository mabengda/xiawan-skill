from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _server_key(base_url: str) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    host_part = parsed.netloc or "default"
    path_part = parsed.path.strip("/")
    raw = host_part if not path_part else f"{host_part}_{path_part.replace('/', '_')}"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw)


def account_store_root() -> Path:
    return Path.home() / ".xiawan" / "accounts"


def account_file_path(base_url: str, username: str) -> Path:
    return account_store_root() / _server_key(base_url) / f"{_normalize_username(username)}.json"


def load_account_record(base_url: str, username: str) -> dict[str, Any] | None:
    path = account_file_path(base_url, username)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def save_account_record(
        *,
        base_url: str,
        username: str,
        agent: dict[str, Any] | None = None,
        registered: bool | None = None,
) -> Path:
    path = account_file_path(base_url, username)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = load_account_record(base_url, username) or {}
    now = _utc_now_iso()

    payload: dict[str, Any] = {
        "username": _normalize_username(username),
        "baseUrl": base_url.rstrip("/"),
        "accountKnown": True,
        "lastSeenAt": now,
    }
    payload.update(existing)
    payload["username"] = _normalize_username(username)
    payload["baseUrl"] = base_url.rstrip("/")
    payload["accountKnown"] = True
    payload["lastSeenAt"] = now

    if registered:
        payload["registeredAt"] = payload.get("registeredAt") or now
    elif "registeredAt" not in payload:
        payload["registeredAt"] = None

    if agent is not None:
        payload["agent"] = agent
        payload["lastAuthenticatedAt"] = now

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
