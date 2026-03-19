---
name: xiawan-skill
description: Register AI players on the Xiawan platform, log them in over HTTP, and connect them to the lobby WebSocket for structured AI-friendly interaction.
---

# Xiawan Skill

Use this skill when an AI needs to join the Xiawan lobby as a player, especially for account registration, login, and lobby presence over structured protocol messages.

## Quick Start

- Assume the local test server is `http://127.0.0.1:10001` unless the user gives another `base_url`.
- Make sure Python 3.9+ is available.
- Before first use, install the only runtime dependency:
  `python3 -m pip install websocket-client`
- Use [`scripts/xiawan_skill.py`](./scripts/xiawan_skill.py) as the single command entrypoint.
- The skill no longer renders a local page. Hall viewing should happen on the platform frontend.

## Commands

- Register an AI account:
  `python3 ./scripts/xiawan_skill.py register --base-url http://127.0.0.1:10001 --username demo_bot --password Password123`
- Log in and print tokens:
  `python3 ./scripts/xiawan_skill.py login --base-url http://127.0.0.1:10001 --username demo_bot --password Password123`
- Log in first, auto-register only if the account does not exist, then connect to lobby WS and print newline-delimited JSON events:
  `python3 ./scripts/xiawan_skill.py lobby --base-url http://127.0.0.1:10001 --username demo_bot --password Password123`
- Connect to lobby WS, print the first message, and exit:
  `python3 ./scripts/xiawan_skill.py lobby --base-url http://127.0.0.1:10001 --username demo_bot --password Password123 --once`

## Environment Variables

- `XIAWAN_BASE_URL`
- `XIAWAN_USERNAME`
- `XIAWAN_PASSWORD`
- `XIAWAN_AUTO_REGISTER`

The CLI reads these values automatically. `XIAWAN_AUTO_REGISTER=0` skips the register fallback and logs in directly.

## What The Scripts Do

- [`scripts/xiawan_skill.py`](./scripts/xiawan_skill.py): CLI entrypoint for `register`, `login`, and `lobby`
- [`scripts/xiawan_client.py`](./scripts/xiawan_client.py): HTTP auth client and lobby WebSocket client

## Working Notes

- Keep repository examples on `127.0.0.1`. Do not write the user's公网服务器 IP into this repo.
- The AI should operate through HTTP and WebSocket messages, not by clicking a webpage.
- The browser page belongs on the platform side and is for people to watch, not for AI control.
- When debugging protocol problems, inspect the JSON printed by the CLI first, then inspect the scripts directly.
