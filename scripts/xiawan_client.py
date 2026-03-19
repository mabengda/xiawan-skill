from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib import error, request
from urllib.parse import urlparse, urlunparse


class XiawanSkillError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, error_code: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


@dataclass
class AuthSession:
    access_token: str
    refresh_token: str
    expires_in_seconds: int
    agent: dict[str, Any]


@dataclass
class LobbySnapshot:
    online_count: int
    players: list[dict[str, Any]]
    timestamp: str | None = None


class LobbyConnection:
    def __init__(self, ws: Any, *, timeout_error_cls: type[BaseException]) -> None:
        self._ws = ws
        self._timeout_error_cls = timeout_error_cls

    def poll_event(self, timeout: float | None = None) -> dict[str, Any] | None:
        if timeout is not None:
            self._ws.settimeout(timeout)
        try:
            raw = self._ws.recv()
        except self._timeout_error_cls:
            return None
        except Exception as exc:
            raise XiawanSkillError(f"接收大厅消息失败: {exc}") from exc
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return self._parse_json(raw)

    def receive_event(self, timeout: float | None = None) -> dict[str, Any]:
        event = self.poll_event(timeout=timeout)
        if event is None:
            raise XiawanSkillError("等待大厅消息超时")
        return event

    def receive_snapshot(self, timeout: float | None = None) -> LobbySnapshot:
        event = self.receive_event(timeout=timeout)
        if event.get("type") != "LOBBY_SNAPSHOT":
            raise XiawanSkillError(f"期待收到 LOBBY_SNAPSHOT，实际收到 {event.get('type')}")
        return LobbySnapshot(
            online_count=int(event.get("onlineCount", 0)),
            players=list(event.get("players", [])),
            timestamp=event.get("timestamp"),
        )

    def request_snapshot(self) -> None:
        self._send({"type": "REQUEST_SNAPSHOT"})

    def send_ping(self) -> None:
        self._send({"type": "PING"})

    def close(self) -> None:
        self._ws.close()

    def _send(self, payload: dict[str, Any]) -> None:
        try:
            self._ws.send(json.dumps(payload))
        except Exception as exc:
            raise XiawanSkillError(f"发送大厅消息失败: {exc}") from exc

    def _parse_json(self, raw: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise XiawanSkillError(f"大厅返回了无法解析的内容: {raw}") from exc
        if not isinstance(parsed, dict):
            raise XiawanSkillError("大厅返回结构不正确")
        return parsed


class XiawanSkillClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session: AuthSession | None = None

    def register(
        self,
        *,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "username": username,
            "password": password,
        }
        return self._post("/api/agents/register", payload)["data"]

    def login(self, username: str, password: str) -> AuthSession:
        payload = {"username": username, "password": password}
        data = self._post("/api/agents/login", payload)["data"]
        session = AuthSession(
            access_token=data["accessToken"],
            refresh_token=data["refreshToken"],
            expires_in_seconds=int(data["expiresInSeconds"]),
            agent=data["agent"],
        )
        self.session = session
        return session

    def connect_lobby(self) -> LobbyConnection:
        if self.session is None:
            raise XiawanSkillError("当前还没有登录会话")

        try:
            import websocket
        except ImportError as exc:
            raise XiawanSkillError(
                "缺少 websocket-client 依赖，请先运行 `python3 -m pip install websocket-client`"
            ) from exc

        try:
            ws = websocket.create_connection(
                self._lobby_ws_url(),
                timeout=self.timeout,
                header=[
                    f"Authorization: Bearer {self.session.access_token}",
                    "User-Agent: xiawan-skill/0.1.0",
                ],
            )
        except Exception as exc:
            raise XiawanSkillError(f"连接大厅 WebSocket 失败: {exc}") from exc

        return LobbyConnection(ws, timeout_error_cls=websocket.WebSocketTimeoutException)

    def auth_headers(self) -> dict[str, str]:
        if self.session is None:
            raise XiawanSkillError("当前还没有登录会话")
        return {"Authorization": f"Bearer {self.session.access_token}"}

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "xiawan-skill/0.1.0",
            },
        )

        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            payload = self._parse_response_body(raw)
            raise XiawanSkillError(
                payload.get("message", f"HTTP {exc.code}"),
                status_code=exc.code,
                error_code=payload.get("errorCode"),
            ) from exc
        except error.URLError as exc:
            raise XiawanSkillError(f"请求失败: {exc.reason}") from exc

        payload = self._parse_response_body(raw)
        if not payload.get("success", False):
            raise XiawanSkillError(
                payload.get("message", "请求失败"),
                error_code=payload.get("errorCode"),
            )
        return payload

    def _parse_response_body(self, raw: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise XiawanSkillError(f"服务端返回了无法解析的内容: {raw}") from exc
        if not isinstance(parsed, dict):
            raise XiawanSkillError("服务端返回结构不正确")
        return parsed

    def _lobby_ws_url(self) -> str:
        parsed = urlparse(self.base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        path = parsed.path.rstrip("/")
        if not path:
            path = "/ws/lobby"
        else:
            path = f"{path}/ws/lobby"
        return urlunparse((scheme, parsed.netloc, path, "", "", ""))
