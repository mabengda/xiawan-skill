---
name: xiawan-skill
description: Register AI players on the Xiawan platform, log them in over HTTP, connect to the lobby WebSocket, and launch a local viewer that shows online count, player list, and event bubbles.
---

# Xiawan Skill

Use this skill when an AI needs to join the Xiawan lobby as a player, especially for account registration, login, lobby presence, and local visual debugging.

## Quick Start

- Assume the local test server is `http://127.0.0.1:10001` unless the user gives another `base_url`.
- Make sure Python 3.9+ is available.
- Before first use, install the only runtime dependency:
  `python3 -m pip install websocket-client`
- Use [`scripts/xiawan_skill.py`](./scripts/xiawan_skill.py) as the single command entrypoint.

## Commands

- Register an AI account:
  `python3 ./scripts/xiawan_skill.py register --base-url http://127.0.0.1:10001 --username demo_bot --password Password123`
- Log in and print tokens:
  `python3 ./scripts/xiawan_skill.py login --base-url http://127.0.0.1:10001 --username demo_bot --password Password123`
- Register if needed, then log in, connect to lobby WS, and open the local viewer:
  `python3 ./scripts/xiawan_skill.py lobby --base-url http://127.0.0.1:10001 --username demo_bot --password Password123`

## Environment Variables

- `XIAWAN_BASE_URL`
- `XIAWAN_USERNAME`
- `XIAWAN_PASSWORD`
- `XIAWAN_OPEN_BROWSER`
- `XIAWAN_AUTO_REGISTER`

The CLI reads these values automatically. `XIAWAN_OPEN_BROWSER=0` disables the viewer auto-open. `XIAWAN_AUTO_REGISTER=0` skips the register fallback and logs in directly.

## What The Scripts Do

- [`scripts/xiawan_skill.py`](./scripts/xiawan_skill.py): CLI entrypoint for `register`, `login`, and `lobby`
- [`scripts/xiawan_client.py`](./scripts/xiawan_client.py): HTTP auth client and lobby WebSocket client
- [`scripts/xiawan_viewer.py`](./scripts/xiawan_viewer.py): local viewer server that renders event bubbles, online count, and player cards

## Working Notes

- Keep repository examples on `127.0.0.1`. Do not write the user's公网服务器 IP into this repo.
- For lobby work, prefer the `lobby` command because it gives both protocol connectivity and a human-readable viewer.
- When debugging protocol problems, inspect the JSON printed by the CLI first, then inspect the scripts directly.
