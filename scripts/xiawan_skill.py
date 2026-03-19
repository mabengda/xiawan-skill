from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from xiawan_client import XiawanSkillClient
from xiawan_viewer import load_viewer_info, open_url_in_browser, run_lobby_viewer, runtime_dir, viewer_info_path


DEFAULT_BASE_URL = "http://127.0.0.1:10001"
SKILL_ROOT = Path(__file__).resolve().parent.parent


def lobby_pid_path() -> Path:
    configured = os.getenv("XIAWAN_LOBBY_PID_PATH")
    if configured:
        return Path(configured).expanduser()
    return runtime_dir() / "lobby.pid"


def lobby_log_path() -> Path:
    configured = os.getenv("XIAWAN_LOBBY_LOG_PATH")
    if configured:
        return Path(configured).expanduser()
    return runtime_dir() / "lobby.log"


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


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_pid_file() -> int | None:
    path = lobby_pid_path()
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _ensure_lobby_dependency() -> None:
    try:
        import websocket  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("缺少 websocket-client 依赖，请先运行 `python3 -m pip install websocket-client`") from exc


def _build_lobby_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "lobby",
        "--base-url",
        args.base_url,
        "--username",
        args.username,
        "--password",
        args.password,
    ]
    if args.no_browser:
        command.append("--no-browser")
    if args.no_auto_register:
        command.append("--no-auto-register")
    return command


def _wait_for_viewer_file(wait_seconds: float) -> dict[str, object] | None:
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        payload = load_viewer_info()
        if payload:
            return payload
        time.sleep(0.2)
    return None


def _start_lobby_process(args: argparse.Namespace) -> int:
    try:
        _ensure_lobby_dependency()
    except RuntimeError as exc:
        _print_json({"running": False, "message": str(exc)})
        return 1

    existing_pid = _read_pid_file()
    if existing_pid is not None and _process_exists(existing_pid):
        payload = load_viewer_info() or {}
        payload.update(
            {
                "status": "already-running",
                "pid": existing_pid,
                "viewerInfoPath": str(viewer_info_path()),
                "logFile": str(lobby_log_path()),
            }
        )
        _print_json(payload)
        return 0

    runtime_dir().mkdir(parents=True, exist_ok=True)
    if viewer_info_path().exists():
        viewer_info_path().unlink()
    if lobby_pid_path().exists():
        lobby_pid_path().unlink()

    command = _build_lobby_command(args)
    with lobby_log_path().open("ab") as log_file:
        process = subprocess.Popen(
            command,
            cwd=str(SKILL_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    lobby_pid_path().write_text(f"{process.pid}\n", encoding="utf-8")
    viewer_payload = _wait_for_viewer_file(args.wait_seconds)
    result: dict[str, object] = {
        "pid": process.pid,
        "running": process.poll() is None,
        "viewerInfoPath": str(viewer_info_path()),
        "logFile": str(lobby_log_path()),
    }
    if viewer_payload:
        result["viewer"] = viewer_payload
    _print_json(result)
    return 0


def _print_viewer_info() -> int:
    payload = load_viewer_info()
    if payload is None:
        _print_json(
            {
                "found": False,
                "viewerInfoPath": str(viewer_info_path()),
                "message": "还没有可用的 viewer 信息，请先运行 lobby 或 start-lobby",
            }
        )
        return 1
    payload["found"] = True
    payload["viewerInfoPath"] = str(viewer_info_path())
    _print_json(payload)
    return 0


def _open_last_viewer() -> int:
    payload = load_viewer_info()
    if payload is None:
        _print_json(
            {
                "opened": False,
                "viewerInfoPath": str(viewer_info_path()),
                "message": "还没有可用的 viewer 信息，请先运行 lobby 或 start-lobby",
            }
        )
        return 1
    viewer_url = str(payload.get("viewerUrl") or "")
    if not viewer_url:
        _print_json(
            {
                "opened": False,
                "viewerInfoPath": str(viewer_info_path()),
                "message": "viewer 信息里没有 URL",
            }
        )
        return 1
    opened = open_url_in_browser(viewer_url)
    _print_json(
        {
            "opened": opened,
            "viewerUrl": viewer_url,
            "viewerInfoPath": str(viewer_info_path()),
        }
    )
    return 0


def _stop_lobby_process() -> int:
    pid = _read_pid_file()
    if pid is None:
        _print_json({"stopped": False, "message": "没有找到 lobby.pid"})
        return 1
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _print_json({"stopped": False, "pid": pid, "message": "进程已经不存在"})
        return 1
    _print_json({"stopped": True, "pid": pid})
    return 0


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

    start_lobby_parser = subparsers.add_parser("start-lobby", help="后台启动大厅 viewer，并把 viewer 地址写到固定文件")
    _add_common_auth_args(start_lobby_parser)
    start_lobby_parser.add_argument(
        "--no-browser",
        action="store_true",
        default=not _bool_from_string(os.getenv("XIAWAN_OPEN_BROWSER"), True),
        help="不自动打开浏览器窗口",
    )
    start_lobby_parser.add_argument(
        "--no-auto-register",
        action="store_true",
        default=not _bool_from_string(os.getenv("XIAWAN_AUTO_REGISTER"), True),
        help="跳过启动时的自动注册兜底",
    )
    start_lobby_parser.add_argument(
        "--wait-seconds",
        type=float,
        default=12.0,
        help="后台启动后等待 viewer 地址文件的秒数",
    )

    subparsers.add_parser("viewer-info", help="输出最近一次 viewer 地址和状态文件位置")
    subparsers.add_parser("open-viewer", help="打开最近一次保存的 viewer 地址")
    subparsers.add_parser("stop-lobby", help="停止后台 lobby 进程")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "viewer-info":
        raise SystemExit(_print_viewer_info())

    if args.command == "open-viewer":
        raise SystemExit(_open_last_viewer())

    if args.command == "stop-lobby":
        raise SystemExit(_stop_lobby_process())

    _require_common_auth_args(parser, args)

    if args.command == "start-lobby":
        raise SystemExit(_start_lobby_process(args))

    if args.command == "lobby":
        try:
            _ensure_lobby_dependency()
        except RuntimeError as exc:
            _print_json({"running": False, "message": str(exc)})
            raise SystemExit(1)

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
