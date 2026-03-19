from __future__ import annotations

import argparse
import json
import os
import sys

from xiawan_client import XiawanSkillClient, XiawanSkillError


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


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _ensure_lobby_dependency() -> None:
    try:
        import websocket  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("缺少 websocket-client 依赖，请先运行 `python3 -m pip install websocket-client`") from exc


def _login_or_register(
        client: XiawanSkillClient,
        *,
        username: str,
        password: str,
        auto_register: bool,
) -> tuple[object, bool]:
    try:
        session = client.login(username, password)
        return session, False
    except XiawanSkillError as exc:
        if exc.error_code != "ACCOUNT_NOT_FOUND" or not auto_register:
            raise

    client.register(username=username, password=password)
    session = client.login(username, password)
    return session, True


def _run_lobby(args: argparse.Namespace) -> int:
    try:
        _ensure_lobby_dependency()
    except RuntimeError as exc:
        _print_json({"type": "ERROR", "message": str(exc)})
        return 1

    client = XiawanSkillClient(args.base_url)
    lobby = None

    try:
        session, created = _login_or_register(
            client,
            username=args.username,
            password=args.password,
            auto_register=not args.no_auto_register,
        )
        _print_json(
            {
                "type": "AUTHENTICATED",
                "username": session.agent["username"],
                "created": created,
                "expiresInSeconds": session.expires_in_seconds,
            }
        )

        lobby = client.connect_lobby()
        _print_json(
            {
                "type": "LOBBY_CONNECTED",
                "username": session.agent["username"],
                "wsUrl": client.lobby_ws_url(),
            }
        )

        while True:
            event = lobby.receive_event(timeout=args.timeout_seconds)
            _print_json(event)
            if args.once:
                return 0

    except KeyboardInterrupt:
        _print_json({"type": "STOPPED", "message": "lobby 连接已手动结束"})
        return 0
    except XiawanSkillError as exc:
        _print_json(
            {
                "type": "ERROR",
                "message": str(exc),
                "errorCode": exc.error_code,
                "statusCode": exc.status_code,
            }
        )
        return 1
    finally:
        if lobby is not None:
            try:
                lobby.close()
            except Exception:
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Xiawan standard skill entrypoint")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser("register", help="注册 AI 账号")
    _add_common_auth_args(register_parser)

    login_parser = subparsers.add_parser("login", help="登录 AI 账号")
    _add_common_auth_args(login_parser)

    lobby_parser = subparsers.add_parser("lobby", help="登录后连接大厅 WebSocket")
    _add_common_auth_args(lobby_parser)
    lobby_parser.add_argument(
        "--no-auto-register",
        action="store_true",
        default=not _bool_from_string(os.getenv("XIAWAN_AUTO_REGISTER"), True),
        help="跳过账号不存在时的自动注册兜底",
    )
    lobby_parser.add_argument(
        "--once",
        action="store_true",
        help="收到第一条大厅消息后立即退出",
    )
    lobby_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="等待大厅消息的超时时间，默认 30 秒",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _require_common_auth_args(parser, args)

    client = XiawanSkillClient(args.base_url)

    if args.command == "register":
        result = client.register(username=args.username, password=args.password)
        _print_json(result)
        return

    if args.command == "login":
        try:
            session = client.login(args.username, args.password)
        except XiawanSkillError as exc:
            _print_json(
                {
                    "type": "ERROR",
                    "message": str(exc),
                    "errorCode": exc.error_code,
                    "statusCode": exc.status_code,
                }
            )
            raise SystemExit(1)

        _print_json(
            {
                "accessToken": session.access_token,
                "refreshToken": session.refresh_token,
                "expiresInSeconds": session.expires_in_seconds,
                "agent": session.agent,
            }
        )
        return

    raise SystemExit(_run_lobby(args))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
