from __future__ import annotations

import argparse
import os
import sys

from .viewer import run_lobby_viewer


def _bool_from_string(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def lobby_entrypoint() -> None:
    parser = argparse.ArgumentParser(description="Start Xiawan lobby viewer from command line or environment")
    parser.add_argument("--base-url", default=os.getenv("XIAWAN_BASE_URL"))
    parser.add_argument("--username", default=os.getenv("XIAWAN_USERNAME"))
    parser.add_argument("--password", default=os.getenv("XIAWAN_PASSWORD"))
    parser.add_argument(
        "--no-browser",
        action="store_true",
        default=not _bool_from_string(os.getenv("XIAWAN_OPEN_BROWSER"), True),
        help="Do not open the local browser viewer window",
    )
    parser.add_argument(
        "--no-auto-register",
        action="store_true",
        default=not _bool_from_string(os.getenv("XIAWAN_AUTO_REGISTER"), True),
        help="Skip register fallback and login directly",
    )
    args = parser.parse_args()

    missing = [
        name
        for name, value in (
            ("XIAWAN_BASE_URL / --base-url", args.base_url),
            ("XIAWAN_USERNAME / --username", args.username),
            ("XIAWAN_PASSWORD / --password", args.password),
        )
        if not value
    ]
    if missing:
        parser.error("missing required values: " + ", ".join(missing))

    raise SystemExit(
        run_lobby_viewer(
            base_url=args.base_url,
            username=args.username,
            password=args.password,
            auto_register=not args.no_auto_register,
            open_browser=not args.no_browser,
        )
    )


if __name__ == "__main__":
    try:
        lobby_entrypoint()
    except KeyboardInterrupt:
        sys.exit(0)
