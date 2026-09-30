import pytest

from donde_plata.runtime import Settings


def test_settings_require_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "TELEGRAM_BOT_TOKEN",
        "COMMON_PUBLIC_BASE_URL",
        "WEBHOOK_PATH",
        "WEBHOOK_SECRET_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN is required"):
        Settings.from_env()

