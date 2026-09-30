from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route
from telegram import MenuButtonWebApp, Update, WebAppInfo
from telegram.ext import Application

from .mini_app_auth import InvalidInitData, verify_init_data

if TYPE_CHECKING:
    from .runtime import Settings

STATIC_DIR = Path(__file__).with_name("static") / "mini_app"
RESPONSE_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                    "Referrer-Policy": "no-referrer"}


def create_web_application(application: Application, settings: Settings) -> Starlette:
    app_path = settings.mini_app_path

    async def redirect(_request: Request) -> Response:
        return RedirectResponse(app_path)

    def static_file(name: str, media_type: str):
        async def serve(_request: Request) -> Response:
            return FileResponse(STATIC_DIR / name, media_type=media_type,
                                headers=RESPONSE_HEADERS)
        return serve

    async def context(request: Request) -> Response:
        scheme, _, raw = request.headers.get("authorization", "").partition(" ")
        try:
            if scheme.lower() != "tma":
                raise InvalidInitData("Open this app from Telegram.")
            user_id = verify_init_data(raw, settings.bot_token)
        except InvalidInitData as error:
            return JSONResponse({"error": str(error)}, status_code=401,
                                headers=RESPONSE_HEADERS)
        return JSONResponse({"user_id": user_id}, headers=RESPONSE_HEADERS)

    async def webhook(request: Request) -> Response:
        supplied_secret = request.headers.get("x-telegram-bot-api-secret-token", "")
        if not hmac.compare_digest(supplied_secret, settings.webhook_secret_token):
            return Response(status_code=403)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            return Response(status_code=415)
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                return Response(status_code=400)
            update = Update.de_json(payload, application.bot)
            if update is None:
                return Response(status_code=400)
        except (ValueError, TypeError, KeyError, UnicodeError):
            return Response(status_code=400)
        await application.update_queue.put(update)
        return Response(status_code=200)

    @asynccontextmanager
    async def lifespan(_web: Starlette):
        initialized = False
        started = False
        try:
            await application.initialize()
            initialized = True
            await application.start()
            started = True
            await application.bot.set_webhook(url=settings.webhook_url,
                                              secret_token=settings.webhook_secret_token)
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp("Open App", WebAppInfo(settings.mini_app_url)))
            yield
        finally:
            try:
                if started:
                    await application.stop()
            finally:
                if initialized:
                    await application.shutdown()

    return Starlette(routes=[
        Route(settings.webhook_path, webhook, methods=["POST"]),
        Route(app_path.rstrip("/"), redirect),
        Route(app_path, static_file("index.html", "text/html")),
        Route(app_path + "app.js", static_file("app.js", "application/javascript")),
        Route(app_path + "app.css", static_file("app.css", "text/css")),
        Route(app_path + "api/context", context, methods=["GET"]),
    ], lifespan=lifespan)
