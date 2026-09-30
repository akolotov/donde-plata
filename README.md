# Donde Plata

Minimal Python Telegram bot deployed by webhook through a shared Tailscale Funnel gateway.

## Development

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install ".[dev]"
.venv/bin/python -m pytest -q
```

Copy `.env.example` to `.env` and replace every placeholder. Each staging or production deployment needs a separate Telegram bot token, Compose project name, webhook alias, webhook path, and webhook secret.

The alias must match the corresponding segment in `WEBHOOK_PATH`. The shared gateway must provide the external `tailscale-ingress` Docker network.

```bash
docker compose pull
docker compose up -d
docker compose logs -f bot
```

For a local build:

```bash
docker build -t donde-plata:local .
BOT_IMAGE=donde-plata:local BOT_PULL_POLICY=never docker compose up -d
```
