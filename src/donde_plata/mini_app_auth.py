"""Identify a caller only after verifying Telegram Mini App initData."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from urllib.parse import parse_qsl

MAX_AGE_SECONDS = 300
FUTURE_SKEW_SECONDS = 30


class InvalidInitData(ValueError):
    pass


def verify_init_data(raw: str, bot_token: str, *, now: float | None = None) -> int:
    if not raw or len(raw) > 8192 or re.search(r"%(?![0-9a-fA-F]{2})", raw):
        raise InvalidInitData("Invalid Telegram authorization.")
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True,
                          encoding="utf-8", errors="strict")
    except (ValueError, UnicodeError) as error:
        raise InvalidInitData("Invalid Telegram authorization.") from error
    fields: dict[str, str] = {}
    for key, value in pairs:
        if not key or key in fields:
            raise InvalidInitData("Duplicate or empty authorization field.")
        fields[key] = value
    supplied_hash = fields.pop("hash", "")
    if re.fullmatch(r"[0-9a-fA-F]{64}", supplied_hash) is None:
        raise InvalidInitData("Invalid Telegram authorization hash.")
    check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied_hash.lower()):
        raise InvalidInitData("Invalid Telegram authorization signature.")
    try:
        auth_date = int(fields["auth_date"])
        user = json.loads(fields["user"])
        user_id = user["id"]
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidInitData("Invalid Telegram authorization payload.") from error
    current_time = time.time() if now is None else now
    if auth_date < current_time - MAX_AGE_SECONDS or auth_date > current_time + FUTURE_SKEW_SECONDS:
        raise InvalidInitData("Authorization expired. Reopen the Mini App.")
    if type(user_id) is not int or user_id <= 0:
        raise InvalidInitData("Invalid Telegram user.")
    return user_id
