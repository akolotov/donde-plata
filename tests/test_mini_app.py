"""Unit tests only: no real bot, environment files, or Telegram API calls."""

import asyncio
import hashlib
import hmac
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import pytest
from starlette.testclient import TestClient

from donde_plata.mini_app_auth import InvalidInitData, verify_init_data
from donde_plata.mini_app_web import create_web_application
from donde_plata.runtime import Settings, start

TOKEN = "unit-test-token"


def signed_data(fields: list[tuple[str, str]]) -> str:
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode([*fields, ("hash", digest)])


def authorization(*, age: int = 0) -> str:
    return signed_data([("auth_date", str(int(time.time()) - age)),
                        ("user", '{"id":123}')])


def test_known_independent_signature_vector() -> None:
    # Public Telegram-Mini-Apps/init-data-golang fixture, not a private credential.
    # https://github.com/Telegram-Mini-Apps/init-data-golang/blob/master/validate_test.go
    raw = (
        "user=%7B%22id%22%3A279058397%2C%22first_name%22%3A%22Vladislav%20%2B%20-%20%3F%20%5C%2F%22%2C"
        "%22last_name%22%3A%22Kibenko%22%2C%22username%22%3A%22vdkfrost%22%2C%22language_code%22%3A%22ru%22%2C"
        "%22is_premium%22%3Atrue%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A%5C%2F%5C%2F"
        "t.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2F4FPEE4tmP3ATHa57u6MqTDih13LTOiMoKoLDRG4PnSA.svg%22%7D"
        "&chat_instance=8134722200314281151&chat_type=private&auth_date=1733509682"
        "&signature=TYJxVcisqbWjtodPepiJ6ghziUL94-KNpG8Pau-X7oNNLNBM72APCpi_RKiUlBvcqo5L-LAxIc3dnTzcZX_PDg"
        "&hash=a433d8f9847bd6addcc563bff7cc82c89e97ea0d90c11fe5729cae6796a36d73"
    )
    token = "7342037359:AAHI25ES9xCOMPokpYoz-p8XVrZUdygo2J4"
    assert verify_init_data(raw, token, now=1733509682) == 279058397
    with pytest.raises(InvalidInitData):
        verify_init_data(raw.replace("signature=", "modified="), token, now=1733509682)


def test_signed_extra_fields_and_identity() -> None:
    fields = [("auth_date", "1000"), ("user", '{"id":123}'),
              ("signature", "signed-extra-field"), ("future_key", "a+b")]
    raw = signed_data(fields)
    assert verify_init_data(raw, TOKEN, now=1000) == 123
    with pytest.raises(InvalidInitData):
        verify_init_data(raw.replace("a%2Bb", "modified"), TOKEN, now=1000)


@pytest.mark.parametrize("now", [1301, 969])
def test_rejects_expired_and_future_data(now: int) -> None:
    raw = signed_data([("auth_date", "1000"), ("user", '{"id":123}')])
    with pytest.raises(InvalidInitData):
        verify_init_data(raw, TOKEN, now=now)


@pytest.mark.parametrize("field", ["hash", "user", "auth_date", "signature", "unknown"])
def test_rejects_duplicate_fields(field: str) -> None:
    raw = signed_data([("auth_date", "1000"), ("user", '{"id":123}'),
                       ("signature", "extra"), ("unknown", "extra")])
    with pytest.raises(InvalidInitData):
        verify_init_data(raw + f"&{field}=duplicate", TOKEN, now=1000)


@pytest.mark.parametrize("raw", ["", "user=%ZZ", "x=%FF&hash=abc", "x" * 8193])
def test_rejects_malformed_data(raw: str) -> None:
    with pytest.raises(InvalidInitData):
        verify_init_data(raw, TOKEN, now=1000)


@pytest.mark.parametrize("user", ['{"id":true}', '{"id":"123"}', '{"id":0}',
                                 '{"id":-1}', 'null', '[]', 'invalid-json'])
def test_rejects_invalid_user(user: str) -> None:
    raw = signed_data([("auth_date", "1000"), ("user", user)])
    with pytest.raises(InvalidInitData):
        verify_init_data(raw, TOKEN, now=1000)


@pytest.fixture
def settings() -> Settings:
    return Settings(TOKEN, "https://unit-test.example", "/hooks/unit-test/telegram/webhook",
                    "unit-test-secret", "/apps/unit-test/")


@pytest.fixture
def application():
    return SimpleNamespace(
        bot=SimpleNamespace(set_webhook=AsyncMock(), set_chat_menu_button=AsyncMock()),
        initialize=AsyncMock(), start=AsyncMock(), stop=AsyncMock(), shutdown=AsyncMock(),
        update_queue=asyncio.Queue(),
    )


def test_api_requires_signed_identity_and_never_caches(application, settings) -> None:
    client = TestClient(create_web_application(application, settings))
    path = settings.mini_app_path + "api/context"
    for headers in ({}, {"Authorization": "tma invalid"},
                    {"Authorization": "tma " + authorization(age=301)}):
        assert client.get(path, headers=headers).status_code == 401
    response = client.get(path, headers={"Authorization": "tma " + authorization()})
    assert response.status_code == 200
    assert response.json() == {"user_id": 123}
    assert response.headers["cache-control"] == "no-store"


def test_static_routes_and_canonical_url(application, settings) -> None:
    client = TestClient(create_web_application(application, settings))
    redirect = client.get(settings.mini_app_path.rstrip("/"), follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == settings.mini_app_path
    for filename, content_type in [("", "text/html"), ("app.js", "application/javascript"),
                                   ("app.css", "text/css")]:
        response = client.get(settings.mini_app_path + filename)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(content_type)
    assert client.get(settings.mini_app_path + "../runtime.py").status_code == 404


def test_webhook_secret_json_validation_and_queue(application, settings) -> None:
    client = TestClient(create_web_application(application, settings))
    headers = {"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret_token}
    assert client.post(settings.webhook_path, json={"update_id": 7}).status_code == 403
    assert client.post(settings.webhook_path, headers=headers, content="bad").status_code == 415
    for payload in ([], {"message": {}}):
        assert client.post(settings.webhook_path, headers=headers, json=payload).status_code == 400
    assert client.post(settings.webhook_path, headers=headers, json={"update_id": 7}).status_code == 200
    assert application.update_queue.get_nowait().update_id == 7
    assert application.update_queue.empty()


def test_lifecycle_and_default_launch_menu(application, settings) -> None:
    with TestClient(create_web_application(application, settings)):
        application.initialize.assert_awaited_once()
        application.start.assert_awaited_once()
        application.bot.set_webhook.assert_awaited_once_with(
            url=settings.webhook_url, secret_token=settings.webhook_secret_token)
        menu = application.bot.set_chat_menu_button.call_args.kwargs["menu_button"]
        assert menu.text == "Open App"
        assert menu.web_app.url == settings.mini_app_url
        application.stop.assert_not_awaited()
    application.stop.assert_awaited_once()
    application.shutdown.assert_awaited_once()


@pytest.mark.parametrize("stage", ["start", "set_webhook", "set_chat_menu_button"])
def test_cleans_up_partial_startup(application, settings, stage: str) -> None:
    target = getattr(application, stage, None) or getattr(application.bot, stage)
    target.side_effect = RuntimeError("unit-test startup failure")
    with pytest.raises(RuntimeError, match="unit-test startup failure"):
        with TestClient(create_web_application(application, settings)):
            pass
    application.shutdown.assert_awaited_once()
    if stage == "start":
        application.stop.assert_not_awaited()
    else:
        application.stop.assert_awaited_once()


def test_shutdown_runs_even_if_stop_fails(application, settings) -> None:
    application.stop.side_effect = RuntimeError("unit-test stop failure")
    with pytest.raises(RuntimeError, match="unit-test stop failure"):
        with TestClient(create_web_application(application, settings)):
            pass
    application.shutdown.assert_awaited_once()


@pytest.mark.parametrize("chat_type", ["private", "group"])
def test_start_button_is_private_chat_only(settings, chat_type: str) -> None:
    reply = AsyncMock()
    update = SimpleNamespace(effective_message=SimpleNamespace(reply_text=reply),
                             effective_chat=SimpleNamespace(type=chat_type))
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"mini_app_url": settings.mini_app_url}))
    asyncio.run(start(update, context))
    kwargs = reply.call_args.kwargs
    if chat_type == "private":
        assert kwargs["reply_markup"].inline_keyboard[0][0].web_app.url == settings.mini_app_url
    else:
        assert "reply_markup" not in kwargs


@pytest.fixture
def environment(monkeypatch):
    values = {"TELEGRAM_BOT_TOKEN": TOKEN, "COMMON_PUBLIC_BASE_URL": "https://unit-test.example/",
              "WEBHOOK_DOCKER_ALIAS": "unit-test", "WEBHOOK_PATH": "/hooks/unit-test/telegram/webhook",
              "WEBHOOK_SECRET_TOKEN": "unit-test-secret"}
    for name in ("MINI_APP_PATH", "WEBHOOK_PUBLIC_BASE_URL", "WEBHOOK_LISTEN_PORT",
                 "WEBHOOK_LISTEN_HOST", "LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_common_origin_builds_both_urls(environment) -> None:
    configured = Settings.from_env()
    assert configured.webhook_url == "https://unit-test.example/hooks/unit-test/telegram/webhook"
    assert configured.mini_app_url == "https://unit-test.example/apps/unit-test/"


@pytest.mark.parametrize("origin", ["http://example.com", "https://example.com/app",
                                   "https://example.com?x=1", "https://example.com#fragment",
                                   "https://user:password@example.com", "https://example.com:bad"])
def test_rejects_invalid_common_origin(environment, monkeypatch, origin: str) -> None:
    monkeypatch.setenv("COMMON_PUBLIC_BASE_URL", origin)
    with pytest.raises(RuntimeError, match="COMMON_PUBLIC_BASE_URL"):
        Settings.from_env()


def test_no_old_origin_fallback(environment, monkeypatch) -> None:
    monkeypatch.delenv("COMMON_PUBLIC_BASE_URL")
    monkeypatch.setenv("WEBHOOK_PUBLIC_BASE_URL", "https://old.example")
    with pytest.raises(RuntimeError, match="COMMON_PUBLIC_BASE_URL is required"):
        Settings.from_env()


@pytest.mark.parametrize("name,value", [("MINI_APP_PATH", "/apps/other/"),
                                       ("WEBHOOK_PATH", "/hooks/other/telegram/webhook"),
                                       ("WEBHOOK_DOCKER_ALIAS", "invalid/alias"),
                                       ("WEBHOOK_SECRET_TOKEN", "bad secret"),
                                       ("WEBHOOK_LISTEN_PORT", "0")])
def test_rejects_invalid_route_secret_or_port(environment, monkeypatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match=name):
        Settings.from_env()
