from __future__ import annotations

import copy
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from queue import Empty, Queue
import threading
from typing import Any
import webbrowser

from .client import LobbySnapshot, XiawanSkillClient, XiawanSkillError


VIEWER_HTML = """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>虾丸 Skill Viewer</title>
    <style>
      :root {
        --bg: #f4efe6;
        --panel: rgba(255, 252, 247, 0.88);
        --panel-strong: #fffaf2;
        --ink: #1c2630;
        --muted: #6c7a86;
        --line: rgba(28, 38, 48, 0.08);
        --accent: #0f8c7d;
        --accent-soft: rgba(15, 140, 125, 0.12);
        --warm: #d57a31;
        --warm-soft: rgba(213, 122, 49, 0.14);
        --danger: #c4514f;
        --danger-soft: rgba(196, 81, 79, 0.14);
        --shadow: 0 22px 60px rgba(35, 48, 61, 0.12);
      }

      * { box-sizing: border-box; }

      body {
        margin: 0;
        min-height: 100vh;
        font-family: "Avenir Next", "SF Pro Rounded", "Segoe UI", sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(15, 140, 125, 0.18), transparent 28%),
          radial-gradient(circle at bottom right, rgba(213, 122, 49, 0.20), transparent 30%),
          linear-gradient(160deg, #f7f1e8 0%, #efe7db 100%);
      }

      .shell {
        width: min(1180px, calc(100vw - 32px));
        margin: 20px auto;
        display: grid;
        gap: 18px;
      }

      .hero {
        background: linear-gradient(135deg, rgba(255, 250, 242, 0.96), rgba(252, 244, 233, 0.90));
        border: 1px solid rgba(255, 255, 255, 0.65);
        border-radius: 28px;
        box-shadow: var(--shadow);
        overflow: hidden;
      }

      .hero-inner {
        padding: 24px;
        display: grid;
        gap: 20px;
      }

      .hero-top {
        display: flex;
        justify-content: space-between;
        align-items: start;
        gap: 16px;
      }

      .eyebrow {
        font-size: 12px;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 10px;
      }

      h1 {
        margin: 0;
        font-size: clamp(30px, 4vw, 46px);
        line-height: 1.02;
      }

      .subtitle {
        margin-top: 10px;
        color: var(--muted);
        font-size: 15px;
      }

      .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 10px 14px;
        border-radius: 999px;
        background: var(--accent-soft);
        color: var(--accent);
        font-weight: 700;
      }

      .status-badge.error {
        background: var(--danger-soft);
        color: var(--danger);
      }

      .status-badge.warn {
        background: var(--warm-soft);
        color: var(--warm);
      }

      .metrics {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
      }

      .metric {
        background: rgba(255, 255, 255, 0.72);
        border: 1px solid rgba(255, 255, 255, 0.6);
        border-radius: 20px;
        padding: 16px 18px;
      }

      .metric-label {
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
      }

      .metric-value {
        margin-top: 10px;
        font-size: 28px;
        font-weight: 800;
      }

      .grid {
        display: grid;
        grid-template-columns: 1.15fr 0.85fr;
        gap: 18px;
      }

      .panel {
        background: var(--panel);
        border: 1px solid rgba(255, 255, 255, 0.62);
        border-radius: 24px;
        box-shadow: var(--shadow);
        overflow: hidden;
        backdrop-filter: blur(12px);
      }

      .panel-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        padding: 18px 20px 0;
      }

      .panel-title {
        font-size: 18px;
        font-weight: 800;
      }

      .panel-subtitle {
        font-size: 13px;
        color: var(--muted);
      }

      .controls {
        display: flex;
        gap: 10px;
      }

      button {
        border: 0;
        border-radius: 999px;
        padding: 10px 14px;
        font: inherit;
        font-weight: 700;
        cursor: pointer;
        color: white;
        background: linear-gradient(135deg, #0f8c7d, #10695f);
        box-shadow: 0 12px 26px rgba(15, 140, 125, 0.22);
      }

      button.secondary {
        background: linear-gradient(135deg, #d57a31, #b45b1a);
        box-shadow: 0 12px 26px rgba(213, 122, 49, 0.22);
      }

      .timeline {
        padding: 18px 20px 22px;
        display: grid;
        gap: 12px;
        max-height: 62vh;
        overflow: auto;
      }

      .bubble {
        display: grid;
        gap: 6px;
        padding: 14px 16px;
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.92);
        border: 1px solid var(--line);
        animation: rise 180ms ease-out;
      }

      .bubble.command { border-left: 4px solid var(--warm); }
      .bubble.success { border-left: 4px solid var(--accent); }
      .bubble.error { border-left: 4px solid var(--danger); }
      .bubble.info,
      .bubble.event { border-left: 4px solid #7e8b98; }

      .bubble-top {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: center;
      }

      .bubble-title {
        font-weight: 800;
      }

      .bubble-time {
        color: var(--muted);
        font-size: 12px;
        white-space: nowrap;
      }

      .bubble-detail {
        color: #40505d;
        line-height: 1.5;
        word-break: break-word;
      }

      .players {
        padding: 18px 20px 22px;
        display: grid;
        gap: 12px;
      }

      .player-card {
        background: rgba(255, 255, 255, 0.90);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 14px 16px;
        display: grid;
        gap: 8px;
      }

      .player-name {
        font-size: 18px;
        font-weight: 800;
      }

      .player-meta {
        color: var(--muted);
        font-size: 13px;
      }

      .empty {
        padding: 18px;
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.78);
        border: 1px dashed rgba(28, 38, 48, 0.16);
        color: var(--muted);
      }

      @keyframes rise {
        from {
          opacity: 0;
          transform: translateY(6px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      @media (max-width: 920px) {
        .metrics,
        .grid {
          grid-template-columns: 1fr;
        }

        .hero-top,
        .panel-head {
          flex-direction: column;
          align-items: start;
        }

        .controls {
          width: 100%;
          flex-wrap: wrap;
        }

        button {
          flex: 1 1 180px;
        }
      }
    </style>
  </head>
  <body>
    <div class="shell">
      <section class="hero">
        <div class="hero-inner">
          <div class="hero-top">
            <div>
              <div class="eyebrow">Xiawan Skill Viewer</div>
              <h1 id="hero-title">Skill 正在启动</h1>
              <div class="subtitle" id="hero-subtitle">等待运行状态...</div>
            </div>
            <div id="status-badge" class="status-badge">准备中</div>
          </div>
          <div class="metrics">
            <div class="metric">
              <div class="metric-label">在线人数</div>
              <div class="metric-value" id="online-count">0</div>
            </div>
            <div class="metric">
              <div class="metric-label">玩家卡片</div>
              <div class="metric-value" id="player-count">0</div>
            </div>
            <div class="metric">
              <div class="metric-label">事件气泡</div>
              <div class="metric-value" id="event-count">0</div>
            </div>
            <div class="metric">
              <div class="metric-label">最近快照</div>
              <div class="metric-value" id="snapshot-time" style="font-size:20px;">-</div>
            </div>
          </div>
        </div>
      </section>

      <section class="grid">
        <article class="panel">
          <div class="panel-head">
            <div>
              <div class="panel-title">执行时间线</div>
              <div class="panel-subtitle">每个命令和服务端回包都会在这里留下气泡</div>
            </div>
            <div class="controls">
              <button type="button" onclick="sendCommand('REQUEST_SNAPSHOT')">刷新快照</button>
              <button type="button" class="secondary" onclick="sendCommand('PING')">发送 Ping</button>
            </div>
          </div>
          <div class="timeline" id="timeline"></div>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <div class="panel-title">大厅玩家</div>
              <div class="panel-subtitle" id="players-subtitle">等待大厅连接...</div>
            </div>
          </div>
          <div class="players" id="players"></div>
        </article>
      </section>
    </div>

    <script>
      let lastEventCount = -1;

      function formatTime(value) {
        if (!value) {
          return '-';
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
          return value;
        }
        return date.toLocaleTimeString('zh-CN', { hour12: false });
      }

      function escapeHtml(value) {
        return String(value)
          .replaceAll('&', '&amp;')
          .replaceAll('<', '&lt;')
          .replaceAll('>', '&gt;')
          .replaceAll('"', '&quot;')
          .replaceAll("'", '&#039;');
      }

      function renderStatus(agent) {
        const badge = document.getElementById('status-badge');
        badge.textContent = agent.statusLabel;
        badge.className = 'status-badge';
        if (agent.status === 'error') {
          badge.classList.add('error');
        } else if (agent.status === 'starting' || agent.status === 'registering' || agent.status === 'logging-in') {
          badge.classList.add('warn');
        }
      }

      function renderPlayers(players) {
        const container = document.getElementById('players');
        if (!players.length) {
          container.innerHTML = '<div class="empty">大厅里暂时还没有在线玩家。</div>';
          return;
        }
        container.innerHTML = players.map((player) => `
          <div class="player-card">
            <div class="player-name">${escapeHtml(player.displayName || player.username)}</div>
            <div class="player-meta">账号：${escapeHtml(player.username)}</div>
            <div class="player-meta">连接时间：${escapeHtml(formatTime(player.connectedAt))}</div>
            <div class="player-meta">最近活跃：${escapeHtml(formatTime(player.lastSeenAt))}</div>
          </div>
        `).join('');
      }

      function renderEvents(events) {
        if (events.length === lastEventCount) {
          return;
        }
        lastEventCount = events.length;
        const container = document.getElementById('timeline');
        if (!events.length) {
          container.innerHTML = '<div class="empty">Skill 已启动，等待第一条事件...</div>';
          return;
        }
        container.innerHTML = events.slice().reverse().map((event) => `
          <div class="bubble ${escapeHtml(event.kind)}">
            <div class="bubble-top">
              <div class="bubble-title">${escapeHtml(event.title)}</div>
              <div class="bubble-time">${escapeHtml(formatTime(event.timestamp))}</div>
            </div>
            <div class="bubble-detail">${escapeHtml(event.detail)}</div>
          </div>
        `).join('');
      }

      async function sendCommand(command) {
        await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command }),
        });
      }

      async function refresh() {
        const response = await fetch('/api/state', { cache: 'no-store' });
        const state = await response.json();
        document.getElementById('hero-title').textContent = state.agent.username;
        document.getElementById('hero-subtitle').textContent = state.agent.subtitle;
        document.getElementById('online-count').textContent = state.lobby.onlineCount;
        document.getElementById('player-count').textContent = state.lobby.players.length;
        document.getElementById('event-count').textContent = state.events.length;
        document.getElementById('snapshot-time').textContent = formatTime(state.lobby.lastSnapshotAt);
        document.getElementById('players-subtitle').textContent = state.lobby.connected
          ? `当前连接正常，最新快照时间 ${formatTime(state.lobby.lastSnapshotAt)}`
          : '大厅尚未建立连接';
        renderStatus(state.agent);
        renderPlayers(state.lobby.players);
        renderEvents(state.events);
      }

      refresh();
      setInterval(refresh, 800);
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

    def start(self) -> str:
        self._thread.start()
        url = self.viewer_url
        self._state.set_viewer_url(url)
        if self._open_browser:
            webbrowser.open(url)
        return url

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
    viewer_url = server.start()
    print(json.dumps({"viewerUrl": viewer_url, "username": username}, ensure_ascii=False, indent=2))

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
        state.set_status("connected", "大厅在线", "WebSocket 已连接，等待大厅快照")
        state.push_event("success", "大厅已连接", "后续每次快照更新都会显示成事件气泡")

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
        state.set_status("error", "发生错误", str(exc))
        state.push_event("error", "Skill 发生错误", str(exc))
        return 1
    finally:
        if lobby is not None:
            state.set_lobby_connected(False)
            try:
                lobby.close()
            except Exception:
                pass
        server.stop()
