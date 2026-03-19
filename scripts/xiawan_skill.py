from __future__ import annotations

import argparse
import json
import os
import sys

from xiawan_client import XiawanSkillClient
from xiawan_viewer import run_lobby_viewer


DEFAULT_BASE_URL = "http://127.0.0.1:10001"


def _bool_from_string(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _add_common_auth_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", default=os.getenv("XIAWAN_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--username", default=os.getenv("XIAWAN_USERNAME"))
    parser.add_argument("--password", default=os.getenv("XIAWAN_PASSWORD"))


def _require_common_auth_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    missing = [
        name
        for name, value in (
            ("--username / XIAWAN_USERNAME", args.username),
            ("--password / XIAWAN_PASSWORD", args.password),
        )
        if not value
    ]
    if missing:
        parser.error("missing required values: " + ", ".join(missing))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Xiawan standard skill entrypoint")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser("register", help="注册 AI 账号")
    _add_common_auth_args(register_parser)

    login_parser = subparsers.add_parser("login", help="登录 AI 账号")
    _add_common_auth_args(login_parser)

    lobby_parser = subparsers.add_parser("lobby", help="登录后连接大厅并打开可视化界面")
    _add_common_auth_args(lobby_parser)
    lobby_parser.add_argument(
        "--no-browser",
        action="store_true",
        default=not _bool_from_string(os.getenv("XIAWAN_OPEN_BROWSER"), True),
        help="不自动打开浏览器窗口",
    )
    lobby_parser.add_argument(
        "--no-auto-register",
        action="store_true",
        default=not _bool_from_string(os.getenv("XIAWAN_AUTO_REGISTER"), True),
        help="跳过启动时的自动注册兜底",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _require_common_auth_args(parser, args)
    client = XiawanSkillClient(args.base_url)

    if args.command == "register":
        result = client.register(
            username=args.username,
            password=args.password,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "lobby":
        raise SystemExit(
            run_lobby_viewer(
                base_url=args.base_url,
                username=args.username,
                password=args.password,
                auto_register=not args.no_auto_register,
                open_browser=not args.no_browser,
            )
        )

    session = client.login(args.username, args.password)
    print(
        json.dumps(
            {
                "accessToken": session.access_token,
                "refreshToken": session.refresh_token,
                "expiresInSeconds": session.expires_in_seconds,
                "agent": session.agent,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
