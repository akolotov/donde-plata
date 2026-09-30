from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import uvicorn
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from .mini_app_web import create_web_application


@dataclass(frozen=True)
class Settings:
    bot_token: str
    common_public_base_url: str
    webhook_path: str
    webhook_secret_token: str
    mini_app_path: str
    listen_host: str = "0.0.0.0"
    listen_port: int = 8080
    log_level: str = "INFO"

    @property
    def webhook_url(self) -> str:
        return self.common_public_base_url + self.webhook_path

    @property
    def mini_app_url(self) -> str:
        return self.common_public_base_url + self.mini_app_path

    @classmethod
    def from_env(cls) -> "Settings":
        def required(name: str) -> str:
            value = os.environ.get(name, "").strip()
            if not value:
                raise RuntimeError(f"{name} is required")
            return value

        token = required("TELEGRAM_BOT_TOKEN")
        origin = required("COMMON_PUBLIC_BASE_URL").rstrip("/")
        try:
            parsed = urlsplit(origin)
            valid_origin = (
                parsed.scheme == "https" and parsed.hostname
                and not parsed.username and not parsed.password and not parsed.path
                and not parsed.query and not parsed.fragment
                and (parsed.port is None or 1 <= parsed.port <= 65535)
                and "?" not in origin and "#" not in origin
                and not any(character.isspace() for character in origin)
            )
        except ValueError:
            valid_origin = False
        if not valid_origin:
            raise RuntimeError("COMMON_PUBLIC_BASE_URL must be an HTTPS origin")

        alias = required("WEBHOOK_DOCKER_ALIAS")
        if re.fullmatch(r"[a-z0-9][a-z0-9_-]*", alias) is None:
            raise RuntimeError("WEBHOOK_DOCKER_ALIAS is invalid")
        webhook_path = required("WEBHOOK_PATH")
        if re.fullmatch(rf"/hooks/{re.escape(alias)}/[A-Za-z0-9/_-]+", webhook_path) is None:
            raise RuntimeError("WEBHOOK_PATH must be /hooks/<WEBHOOK_DOCKER_ALIAS>/<route>")
        app_path = os.environ.get("MINI_APP_PATH", f"/apps/{alias}/").strip()
        if app_path != f"/apps/{alias}/":
            raise RuntimeError("MINI_APP_PATH must be /apps/<WEBHOOK_DOCKER_ALIAS>/")
        secret = required("WEBHOOK_SECRET_TOKEN")
        if re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret) is None:
            raise RuntimeError("WEBHOOK_SECRET_TOKEN must contain 1-256 letters, digits, _ or -")
        try:
            port = int(os.environ.get("WEBHOOK_LISTEN_PORT", "8080"))
        except ValueError as error:
            raise RuntimeError("WEBHOOK_LISTEN_PORT must be an integer") from error
        if not 1 <= port <= 65535:
            raise RuntimeError("WEBHOOK_LISTEN_PORT must be between 1 and 65535")
        return cls(token, origin, webhook_path, secret, app_path,
                   os.environ.get("WEBHOOK_LISTEN_HOST", "0.0.0.0"), port,
                   os.environ.get("LOG_LEVEL", "INFO"))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None or update.effective_chat is None:
        return
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text("Open a private chat with the bot to launch the app.")
        return
    url = context.application.bot_data["mini_app_url"]
    await update.effective_message.reply_text(
        "Open the app to get started.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Open App", web_app=WebAppInfo(url))]
        ]),
    )


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(level=settings.log_level.upper())
    # HTTP request logs include the token in Telegram API URLs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    application = ApplicationBuilder().token(settings.bot_token).updater(None).build()
    application.bot_data["mini_app_url"] = settings.mini_app_url
    application.add_handler(CommandHandler("start", start))
    uvicorn.run(create_web_application(application, settings),
                host=settings.listen_host, port=settings.listen_port)


if __name__ == "__main__":
    main()
