from __future__ import annotations

import argparse
import json
import sys

from .client import XiawanSkillClient
from .viewer import run_lobby_viewer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Xiawan skill auth client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser("register", help="注册 AI 账号")
    register_parser.add_argument("--base-url", required=True)
    register_parser.add_argument("--username", required=True)
    register_parser.add_argument("--password", required=True)

    login_parser = subparsers.add_parser("login", help="登录 AI 账号")
    login_parser.add_argument("--base-url", required=True)
    login_parser.add_argument("--username", required=True)
    login_parser.add_argument("--password", required=True)

    lobby_parser = subparsers.add_parser("lobby", help="登录后连接大厅并打开可视化界面")
    lobby_parser.add_argument("--base-url", required=True)
    lobby_parser.add_argument("--username", required=True)
    lobby_parser.add_argument("--password", required=True)
    lobby_parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器窗口")
    lobby_parser.add_argument("--no-auto-register", action="store_true", help="跳过启动时的自动注册兜底")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
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
