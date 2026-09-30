# Donde Plata

Donde Plata is a family finance assistant designed to bring both partners' income, expenses, and balances into one place. The goal is to reduce manual bookkeeping and make it easy to understand where money goes, how spending compares with the family budget, and how much savings earn.

## How it works

The assistant provides two ways to work with the same financial records inside Telegram:

- **Telegram bot:** a chat with a program. Send it a bank statement, a payment screenshot, or a message about a purchase. The assistant is intended to record transactions, ask for clarification when needed, and send regular financial summaries.
- **Telegram Mini App:** an interactive application that opens inside Telegram. It provides space for browsing transaction history, managing accounts and expense categories, and planning budgets.

Telegram makes it convenient for both partners to share documents directly from their banking apps and use the assistant on their existing devices.

## Planned capabilities

- Track income, expenses, and transfers across bank accounts, cash, and cryptocurrency holdings in multiple currencies. Transfers between family accounts should not inflate income or spending.
- Import transactions from statements, screenshots, bank notification emails, and text messages. Use AI where needed to interpret data, suggest expense tags, or match the two sides of a transfer, with user clarification for uncertain cases.
- Organize expenses with multiple tags and compare actual spending with monthly and annual budgets.
- Send regular summaries showing spending, budget progress, and savings income, and help record recurring payments.
- Track interest, cashback, and earnings from cryptocurrency lending separately from deposits and withdrawals.
- Support shared and private accounts, reconcile recorded balances with actual balances, and keep a history of changes.

These capabilities describe the product direction. The current repository provides a minimal Python Telegram bot and Mini App scaffold served through a shared Tailscale Funnel gateway; the finance features are not yet implemented.

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
