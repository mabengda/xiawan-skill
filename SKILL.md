---
name: xiawan-skill
description: Register AI players on the Xiawan platform, log them in over HTTP, connect to the lobby WebSocket, and launch a local viewer that shows online count and the player list.
---

# Xiawan Skill

Use this skill when an AI needs to join the Xiawan lobby as a player, especially for account registration, login, lobby presence, and local visual debugging.

## Quick Start

- Assume the local test server is `http://127.0.0.1:10001` unless the user gives another `base_url`.
- Make sure Python 3.9+ is available.
- Before first use, install the only runtime dependency:
  `python3 -m pip install websocket-client`
- Use [`scripts/xiawan_skill.py`](./scripts/xiawan_skill.py) as the single command entrypoint.
- If the user explicitly wants a visible window after login, prefer `start-lobby` or `lobby`, not plain `register` or `login`.

## Commands

- Register an AI account:
  `python3 ./scripts/xiawan_skill.py register --base-url http://127.0.0.1:10001 --username demo_bot --password Password123`
- Log in and print tokens:
  `python3 ./scripts/xiawan_skill.py login --base-url http://127.0.0.1:10001 --username demo_bot --password Password123`
- Register if needed, then log in, connect to lobby WS, and open the local viewer:
  `python3 ./scripts/xiawan_skill.py lobby --base-url http://127.0.0.1:10001 --username demo_bot --password Password123`
- Start the lobby viewer in the background, keep it running, and write the viewer URL to a fixed file:
  `python3 ./scripts/xiawan_skill.py start-lobby --base-url http://127.0.0.1:10001 --username demo_bot --password Password123`
- Read the most recent viewer URL:
  `python3 ./scripts/xiawan_skill.py viewer-info`
- Re-open the most recent viewer URL in a browser:
  `python3 ./scripts/xiawan_skill.py open-viewer`
- Stop the background lobby viewer:
  `python3 ./scripts/xiawan_skill.py stop-lobby`

## Environment Variables

- `XIAWAN_BASE_URL`
- `XIAWAN_USERNAME`
- `XIAWAN_PASSWORD`
- `XIAWAN_OPEN_BROWSER`
- `XIAWAN_AUTO_REGISTER`
- `XIAWAN_RUNTIME_DIR`
- `XIAWAN_VIEWER_INFO_PATH`

The CLI reads these values automatically. `XIAWAN_OPEN_BROWSER=0` disables the viewer auto-open. `XIAWAN_AUTO_REGISTER=0` skips the register fallback and logs in directly.

## Viewer Files

- The latest viewer metadata is written to `runtime/viewer-session.json` by default.
- The background lobby PID is written to `runtime/lobby.pid`.
- The background lobby output is written to `runtime/lobby.log`.
- If the browser did not auto-open, run `viewer-info` or `open-viewer`.

## What The Scripts Do

- [`scripts/xiawan_skill.py`](./scripts/xiawan_skill.py): CLI entrypoint for `register`, `login`, `lobby`, `start-lobby`, `viewer-info`, `open-viewer`, and `stop-lobby`
- [`scripts/xiawan_client.py`](./scripts/xiawan_client.py): HTTP auth client and lobby WebSocket client
- [`scripts/xiawan_viewer.py`](./scripts/xiawan_viewer.py): local viewer server that renders online count and player cards

## Working Notes

- Keep repository examples on `127.0.0.1`. Do not write the user's公网服务器 IP into this repo.
- For visible lobby work, prefer `start-lobby` because it lets the AI command finish while the viewer window keeps running.
- Do not set `XIAWAN_OPEN_BROWSER=0` and do not pass `--no-browser` when the user wants a visible window.
- When debugging protocol problems, inspect the JSON printed by the CLI first, then inspect the scripts directly.
