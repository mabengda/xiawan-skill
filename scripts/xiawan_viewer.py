from __future__ import annotations

import copy
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
import threading
import traceback
from typing import Any
import webbrowser

from xiawan_client import LobbySnapshot, XiawanSkillClient, XiawanSkillError


def skill_root_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def runtime_dir() -> Path:
    configured = os.getenv("XIAWAN_RUNTIME_DIR")
    if configured:
        return Path(configured).expanduser()
    return skill_root_dir() / "runtime"


def viewer_info_path() -> Path:
    configured = os.getenv("XIAWAN_VIEWER_INFO_PATH")
    if configured:
        return Path(configured).expanduser()
    return runtime_dir() / "viewer-session.json"


def load_viewer_info() -> dict[str, Any] | None:
    path = viewer_info_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_viewer_info(payload: dict[str, Any]) -> Path:
    path = viewer_info_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def open_url_in_browser(url: str) -> bool:
    try:
        if webbrowser.open(url, new=2):
            return True
    except Exception:
        pass

    commands: list[list[str]] = []
    if sys.platform == "darwin":
        commands.append(["open", url])
    elif os.name == "nt":
        commands.append(["cmd", "/c", "start", "", url])
    else:
        commands.append(["xdg-open", url])

    for command in commands:
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            continue
    return False


VIEWER_HTML = """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>虾丸大厅 Viewer</title>
    <style>
      :root {
        --bg: #f5efe4;
        --panel: rgba(255, 251, 245, 0.92);
        --ink: #1c2730;
        --muted: #677784;
        --line: rgba(28, 39, 48, 0.08);
        --accent: #117f70;
        --accent-soft: rgba(17, 127, 112, 0.12);
        --danger: #bf5347;
        --danger-soft: rgba(191, 83, 71, 0.12);
        --shadow: 0 18px 48px rgba(38, 50, 61, 0.12);
      }

      * { box-sizing: border-box; }

      body {
        margin: 0;
        min-height: 100vh;
        font-family: "Avenir Next", "SF Pro Rounded", "Segoe UI", sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(17, 127, 112, 0.18), transparent 28%),
          radial-gradient(circle at bottom right, rgba(212, 132, 55, 0.16), transparent 28%),
          linear-gradient(160deg, #f7f1e8 0%, #eee5d8 100%);
      }

      .shell {
        width: min(900px, calc(100vw - 32px));
        margin: 24px auto;
        display: grid;
        gap: 18px;
      }

      .panel {
        background: var(--panel);
        border: 1px solid rgba(255, 255, 255, 0.68);
        border-radius: 28px;
        box-shadow: var(--shadow);
        backdrop-filter: blur(12px);
      }

      .hero {
        padding: 28px;
        display: grid;
        gap: 22px;
      }

      .eyebrow {
        font-size: 12px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--muted);
      }

      h1 {
        margin: 10px 0 0;
        font-size: clamp(34px, 5vw, 56px);
        line-height: 1;
      }

      .subtitle {
        color: var(--muted);
        margin-top: 10px;
        font-size: 15px;
      }

      .hero-top {
        display: flex;
        justify-content: space-between;
        gap: 18px;
        align-items: start;
      }

      .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 10px 14px;
        border-radius: 999px;
        background: var(--accent-soft);
        color: var(--accent);
        font-weight: 800;
        white-space: nowrap;
      }

      .status-badge.error {
        background: var(--danger-soft);
        color: var(--danger);
      }

      .count-card {
        padding: 28px;
        border-radius: 24px;
        background: linear-gradient(135deg, rgba(17, 127, 112, 0.12), rgba(255, 255, 255, 0.68));
        border: 1px solid rgba(17, 127, 112, 0.10);
      }

      .count-label {
        font-size: 13px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--muted);
      }

      .count-value {
        margin-top: 10px;
        font-size: clamp(52px, 10vw, 96px);
        font-weight: 900;
        line-height: 0.95;
      }

      .count-hint {
        margin-top: 14px;
        color: var(--muted);
        font-size: 14px;
      }

      .players-panel {
        padding: 22px;
      }

      .panel-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 12px;
      }

      .panel-title {
        font-size: 24px;
        font-weight: 900;
      }

      .panel-subtitle {
        color: var(--muted);
        font-size: 14px;
      }

      .players {
        display: grid;
        gap: 12px;
        margin-top: 18px;
      }

      .player-card {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 14px;
        padding: 16px 18px;
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.80);
        border: 1px solid var(--line);
      }

      .player-main {
        min-width: 0;
      }

      .player-name {
        font-size: 18px;
        font-weight: 800;
      }

      .player-id {
        margin-top: 4px;
        color: var(--muted);
        font-size: 14px;
      }

      .player-status {
        padding: 8px 12px;
        border-radius: 999px;
        background: var(--accent-soft);
        color: var(--accent);
        font-size: 13px;
        font-weight: 800;
        white-space: nowrap;
      }

      .empty {
        padding: 22px;
        border-radius: 20px;
        border: 1px dashed rgba(28, 39, 48, 0.14);
        color: var(--muted);
        background: rgba(255, 255, 255, 0.58);
      }

      @media (max-width: 640px) {
        .shell {
          width: min(100vw - 16px, 100%);
          margin: 12px auto;
        }

        .hero,
        .players-panel {
          padding: 18px;
        }

        .hero-top,
        .panel-head,
        .player-card {
          flex-direction: column;
          align-items: flex-start;
        }
      }
    </style>
  </head>
  <body>
    <main class="shell">
      <section class="panel hero">
        <div class="hero-top">
          <div>
            <div class="eyebrow">Xiawan Lobby Viewer</div>
            <h1 id="title">虾丸大厅</h1>
            <div class="subtitle" id="subtitle">准备连接中...</div>
          </div>
          <div class="status-badge" id="status-badge">准备中</div>
        </div>

        <div class="count-card">
          <div class="count-label">在线玩家数量</div>
          <div class="count-value" id="online-count">0</div>
          <div class="count-hint" id="count-hint">正在等待大厅快照...</div>
        </div>
      </section>

      <section class="panel players-panel">
        <div class="panel-head">
          <div class="panel-title">玩家列表</div>
          <div class="panel-subtitle" id="players-subtitle">大厅尚未连接</div>
        </div>
        <div class="players" id="player-list"></div>
      </section>
    </main>

    <script>
      const stateUrl = '/api/state';

      function escapeHtml(value) {
        return String(value ?? '')
          .replaceAll('&', '&amp;')
          .replaceAll('<', '&lt;')
          .replaceAll('>', '&gt;')
          .replaceAll('"', '&quot;')
          .replaceAll("'", '&#39;');
      }

      function formatCount(value) {
        if (value === undefined || value === null) {
          return '0';
        }
        return String(value);
      }

      function renderPlayers(players) {
        const playerList = document.getElementById('player-list');
        if (!Array.isArray(players) || players.length === 0) {
          playerList.innerHTML = '<div class="empty">当前没有在线玩家。</div>';
          return;
        }

        playerList.innerHTML = players
          .map((player) => `
            <article class="player-card">
              <div class="player-main">
                <div class="player-name">${escapeHtml(player.displayName || player.username || '匿名玩家')}</div>
                <div class="player-id">@${escapeHtml(player.username || '-')}</div>
              </div>
              <div class="player-status">${escapeHtml(player.status || 'ONLINE')}</div>
            </article>
          `)
          .join('');
      }

      function renderState(state) {
        if (!state || !state.agent || !state.lobby) {
          return;
        }

        document.getElementById('title').textContent = state.agent.username
          ? `${state.agent.username} 的虾丸大厅`
          : '虾丸大厅';
        document.getElementById('subtitle').textContent = state.agent.subtitle || '';
        document.getElementById('status-badge').textContent = state.agent.statusLabel || '准备中';
        document.getElementById('status-badge').className = `status-badge ${state.agent.status === 'error' ? 'error' : ''}`;
        document.getElementById('online-count').textContent = formatCount(state.lobby.onlineCount);
        document.getElementById('count-hint').textContent = state.lobby.connected
          ? `当前大厅里有 ${formatCount(state.lobby.onlineCount)} 位在线玩家`
          : '大厅连接尚未建立';
        document.getElementById('players-subtitle').textContent = state.lobby.connected
          ? '实时展示当前在线玩家'
          : '大厅尚未连接';

        renderPlayers(state.lobby.players || []);
      }

      async function refreshState() {
        const response = await fetch(stateUrl, { cache: 'no-store' });
        const state = await response.json();
        renderState(state);
      }

      async function boot() {
        await refreshState();
        setInterval(refreshState, 1500);
      }

      boot().catch((error) => {
        console.error(error);
      });
    </script>
  </body>
</html>
"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _preview_players(players: list[dict[str, Any]]) -> str:
    if not players:
        return "暂无在线玩家"
    names = [str(player.get("displayName") or player.get("username") or "unknown") for player in players[:4]]
    suffix = "" if len(players) <= 4 else f" 等 {len(players)} 人"
    return "、".join(names) + suffix


class SkillViewerState:
    def __init__(self, base_url: str, username: str) -> None:
        self._lock = threading.Lock()
        self._commands: Queue[str] = Queue()
        self._next_event_id = 1
        self._state: dict[str, Any] = {
            "agent": {
                "username": username,
                "baseUrl": base_url,
                "status": "starting",
                "statusLabel": "准备中",
                "subtitle": f"正在准备连接 {base_url}",
                "viewerUrl": None,
            },
            "lobby": {
                "connected": False,
                "onlineCount": 0,
                "players": [],
                "lastSnapshotAt": None,
            },
            "events": [],
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def set_viewer_url(self, viewer_url: str) -> None:
        with self._lock:
            self._state["agent"]["viewerUrl"] = viewer_url
            self._state["agent"]["subtitle"] = f"Viewer 已启动：{viewer_url}"

    def set_status(self, status: str, status_label: str, subtitle: str) -> None:
        with self._lock:
            self._state["agent"]["status"] = status
            self._state["agent"]["statusLabel"] = status_label
            self._state["agent"]["subtitle"] = subtitle

    def set_lobby_connected(self, connected: bool) -> None:
        with self._lock:
            self._state["lobby"]["connected"] = connected

    def update_snapshot(self, snapshot: LobbySnapshot) -> None:
        with self._lock:
            self._state["lobby"]["onlineCount"] = snapshot.online_count
            self._state["lobby"]["players"] = list(snapshot.players)
            self._state["lobby"]["lastSnapshotAt"] = snapshot.timestamp or _utc_now_iso()

    def push_event(self, kind: str, title: str, detail: str) -> None:
        with self._lock:
            events = self._state["events"]
            events.append(
                {
                    "id": self._next_event_id,
                    "kind": kind,
                    "title": title,
                    "detail": detail,
                    "timestamp": _utc_now_iso(),
                }
            )
            self._next_event_id += 1
            if len(events) > 80:
                del events[: len(events) - 80]

    def enqueue_command(self, command: str) -> None:
        self._commands.put(command)

    def next_command(self, timeout: float = 0.0) -> str | None:
        try:
            return self._commands.get(timeout=timeout)
        except Empty:
            return None


class SkillViewerServer:
    def __init__(self, state: SkillViewerState, *, open_browser: bool) -> None:
        self._state = state
        self._open_browser = open_browser
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._build_handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def viewer_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def start(self) -> tuple[str, bool]:
        self._thread.start()
        url = self.viewer_url
        self._state.set_viewer_url(url)
        browser_opened = False
        if self._open_browser:
            browser_opened = open_url_in_browser(url)
        return url, browser_opened

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1)

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        state = self._state

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path in {"/", "/index.html"}:
                    self._send_html(VIEWER_HTML)
                    return
                if self.path == "/api/state":
                    self._send_json(state.snapshot())
                    return
                self.send_error(HTTPStatus.NOT_FOUND)

            def do_POST(self) -> None:
                if self.path != "/api/command":
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return

                payload = self._read_json_body()
                command = str(payload.get("command", "")).upper()
                if command not in {"REQUEST_SNAPSHOT", "PING"}:
                    self.send_error(HTTPStatus.BAD_REQUEST, "unsupported command")
                    return

                state.enqueue_command(command)
                self._send_json({"success": True, "command": command})

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _read_json_body(self) -> dict[str, Any]:
                content_length = int(self.headers.get("Content-Length", "0") or "0")
                raw = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    return {}
                return parsed if isinstance(parsed, dict) else {}

            def _send_html(self, html: str) -> None:
                body = html.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_json(self, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler


def _snapshot_from_event(event: dict[str, Any]) -> LobbySnapshot:
    return LobbySnapshot(
        online_count=int(event.get("onlineCount", 0)),
        players=list(event.get("players", [])),
        timestamp=event.get("timestamp"),
    )


def run_lobby_viewer(
    *,
    base_url: str,
    username: str,
    password: str,
    auto_register: bool = True,
    open_browser: bool = True,
) -> int:
    state = SkillViewerState(base_url, username)
    server = SkillViewerServer(state, open_browser=open_browser)
    viewer_url, browser_opened = server.start()
    viewer_payload: dict[str, Any] = {
        "viewerUrl": viewer_url,
        "viewerInfoPath": str(viewer_info_path()),
        "username": username,
        "baseUrl": base_url,
        "pid": os.getpid(),
        "browserOpenRequested": open_browser,
        "browserOpened": browser_opened,
        "startedAt": _utc_now_iso(),
        "connected": False,
    }
    write_viewer_info(viewer_payload)
    print(json.dumps(viewer_payload, ensure_ascii=False, indent=2))
    print(f"VIEWER_URL={viewer_url}", flush=True)
    print(f"VIEWER_INFO_PATH={viewer_payload['viewerInfoPath']}", flush=True)

    client = XiawanSkillClient(base_url)
    lobby = None

    try:
        state.push_event("info", "Skill 启动", f"viewer 已就绪：{viewer_url}")

        if auto_register:
            state.set_status("registering", "注册中", f"正在尝试注册 {username}")
            state.push_event("command", "执行注册", f"向 {base_url} 提交 register")
            try:
                profile = client.register(username=username, password=password)
            except XiawanSkillError as exc:
                if exc.status_code == 409 or exc.error_code == "CONFLICT":
                    state.push_event("info", "账号已存在", "本次跳过注册，直接进入登录流程")
                else:
                    raise
            else:
                state.push_event("success", "注册成功", f"账号 {profile.get('username', username)} 已创建")

        state.set_status("logging-in", "登录中", f"正在登录 {username}")
        state.push_event("command", "执行登录", "提交 username/password 获取 token")
        session = client.login(username, password)
        state.push_event("success", "登录成功", f"access token 有效期 {session.expires_in_seconds} 秒")

        state.set_status("connecting", "连大厅中", "正在建立 WebSocket 大厅连接")
        state.push_event("command", "连接大厅", "准备订阅大厅在线状态和玩家列表")
        lobby = client.connect_lobby()
        state.set_lobby_connected(True)
        viewer_payload["connected"] = True
        viewer_payload["connectedAt"] = _utc_now_iso()
        write_viewer_info(viewer_payload)
        state.set_status("connected", "大厅在线", "WebSocket 已连接，等待大厅快照")
        state.push_event("success", "大厅已连接", "后续会自动更新在线人数和玩家列表")

        while True:
            pending_command = state.next_command(timeout=0.1)
            while pending_command is not None:
                if pending_command == "REQUEST_SNAPSHOT":
                    state.push_event("command", "手动刷新快照", "viewer 发起 REQUEST_SNAPSHOT")
                    lobby.request_snapshot()
                elif pending_command == "PING":
                    state.push_event("command", "发送 Ping", "viewer 发起 PING")
                    lobby.send_ping()
                pending_command = state.next_command(timeout=0.0)

            event = lobby.poll_event(timeout=0.4)
            if event is None:
                continue

            event_type = str(event.get("type", "UNKNOWN"))
            if event_type == "LOBBY_SNAPSHOT":
                snapshot = _snapshot_from_event(event)
                state.update_snapshot(snapshot)
                state.push_event(
                    "event",
                    "大厅快照更新",
                    f"在线 {snapshot.online_count} 人，当前玩家：{_preview_players(snapshot.players)}",
                )
                continue

            if event_type == "PONG":
                state.push_event("event", "收到 Pong", "服务端已响应当前连接")
                continue

            state.push_event("event", f"收到 {event_type}", json.dumps(event, ensure_ascii=False))

    except KeyboardInterrupt:
        state.set_status("stopped", "已停止", "skill 已手动结束")
        state.push_event("info", "Skill 已停止", "可以关闭 viewer 页面了")
        return 0
    except XiawanSkillError as exc:
        message = str(exc)
        state.set_status("error", "发生错误", message)
        state.push_event("error", "Skill 发生错误", message)
        viewer_payload["error"] = message
        viewer_payload["errorAt"] = _utc_now_iso()
        write_viewer_info(viewer_payload)
        print(json.dumps({"error": message, "viewerInfoPath": viewer_payload["viewerInfoPath"]}, ensure_ascii=False), flush=True)
        return 1
    except Exception as exc:
        message = f"未处理异常: {exc}"
        state.set_status("error", "发生错误", message)
        state.push_event("error", "Skill 发生错误", message)
        viewer_payload["error"] = message
        viewer_payload["errorAt"] = _utc_now_iso()
        write_viewer_info(viewer_payload)
        traceback.print_exc()
        return 1
    finally:
        viewer_payload["connected"] = False
        viewer_payload["stoppedAt"] = _utc_now_iso()
        write_viewer_info(viewer_payload)
        if lobby is not None:
            state.set_lobby_connected(False)
            try:
                lobby.close()
            except Exception:
                pass
        server.stop()
