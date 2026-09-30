# Donde Plata

Minimal Python Telegram bot and Mini App served through a shared Tailscale Funnel gateway.

## Development

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install ".[dev]"
.venv/bin/python -m pytest -q
node tests/test_mini_app_ui.js
node --check src/donde_plata/static/mini_app/app.js
```

Tests use stubbed Telegram objects and synthetic authorization data; they do not contact Telegram or start the bot.

## Configuration and deployment

Copy `.env.example` to `.env` and replace every placeholder. `COMMON_PUBLIC_BASE_URL` is the sole public HTTPS origin, without a path, credentials, query, or fragment. The previous webhook-only origin setting is no longer supported; existing deployments must migrate their configuration before running this version.

Each staging or production deployment needs a distinct Telegram bot token, Compose project name, webhook alias, webhook path, and webhook secret. Mini App paths follow the distinct aliases.

The alias must match both `WEBHOOK_PATH` (`/hooks/<alias>/telegram/webhook`) and `MINI_APP_PATH` (`/apps/<alias>/`). Omitting `MINI_APP_PATH` derives it from the alias. Both public URLs are built from the common origin.

The shared gateway must provide the external `tailscale-ingress` Docker network and forward both `/hooks/<alias>/...` and `/apps/<alias>/...` to the bot's single listener on port 8080, preserving paths. Gateway configuration is maintained outside this repository: verify that both routes are supported before deploying. The scaffold does not change the gateway.

On startup, the bot registers its webhook and global **Open App** Telegram menu button. `/start` also offers an inline launch button in private chats. Starting the deployment therefore changes the bot's Telegram webhook and menu settings.

```bash
docker compose pull
docker compose up -d
docker compose logs -f bot
```

Published images are the default. To test local code, reuse the shared local image:

```bash
docker build -t donde-plata:local .
BOT_IMAGE=donde-plata:local BOT_PULL_POLICY=never docker compose up -d
```

## Mini App

The packaged HTML, CSS, and JavaScript load the Telegram WebApp SDK, use Telegram theme colors, and show loading, outside-Telegram, and authorization-error states. The client calls `ready()` and `expand()` and forwards raw `initData` to the same-origin `GET /apps/<alias>/api/context` endpoint using `Authorization: tma <initData>`.

The server verifies Telegram's HMAC signature, rejects duplicate or malformed fields, and validates the signed user ID and authorization date (five minutes maximum age, 30 seconds future clock allowance). The API returns only the verified `user_id`; identity verification does not define a product access policy. The public frontend needs no authentication. Telegram webhook requests independently require the configured webhook secret.

BotFather Main Mini App/profile-button and deep-link setup are outside this scaffold.
