from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes


@dataclass(frozen=True)
class Settings:
    bot_token: str
    public_base_url: str
    webhook_path: str
    webhook_secret_token: str
    listen_host: str = "0.0.0.0"
    listen_port: int = 8080
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        def required(name: str) -> str:
            value = os.environ.get(name, "").strip()
            if not value:
                raise RuntimeError(f"{name} is required")
            return value

        return cls(
            bot_token=required("TELEGRAM_BOT_TOKEN"),
            public_base_url=required("WEBHOOK_PUBLIC_BASE_URL").rstrip("/"),
            webhook_path="/" + required("WEBHOOK_PATH").strip("/"),
            webhook_secret_token=required("WEBHOOK_SECRET_TOKEN"),
            listen_host=os.environ.get("WEBHOOK_LISTEN_HOST", "0.0.0.0"),
            listen_port=int(os.environ.get("WEBHOOK_LISTEN_PORT", "8080")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.effective_message is not None:
        await update.effective_message.reply_text("Donde Plata is running.")


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(level=settings.log_level.upper())
    application = ApplicationBuilder().token(settings.bot_token).build()
    application.add_handler(CommandHandler("start", start))
    application.run_webhook(
        listen=settings.listen_host,
        port=settings.listen_port,
        url_path=settings.webhook_path.lstrip("/"),
        webhook_url=f"{settings.public_base_url}{settings.webhook_path}",
        secret_token=settings.webhook_secret_token,
    )


if __name__ == "__main__":
    main()

