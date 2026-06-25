"""CSRF-защита: подписанный токен (stateless, без request.session)."""

import secrets
import hashlib
import hmac
import os
import re
from urllib.parse import parse_qs

from fastapi import Request, HTTPException


def _get_secret() -> bytes:
    secret = os.getenv("APP_SECRET")
    return secret.encode() if secret else b"superior-crm-csrf-secret"


def get_csrf_token(request: Request) -> str:
    """Сгенерировать подписанный CSRF-токен (stateless)."""
    random_part = secrets.token_hex(16)
    sig = hmac.new(_get_secret(), random_part.encode(), hashlib.sha256).hexdigest()
    return f"{random_part}:{sig}"


def csrf_input(request: Request) -> str:
    """HTML скрытого поля с CSRF-токеном."""
    return f'<input type="hidden" name="_csrf_token" value="{get_csrf_token(request)}" />'


def _validate_csrf(token: str) -> bool:
    """Проверить подпись CSRF-токена."""
    if ":" not in token:
        return False
    random_part, sig = token.split(":", 1)
    expected = hmac.new(_get_secret(), random_part.encode(), hashlib.sha256).hexdigest()
    return secrets.compare_digest(expected, sig)


def _extract_csrf_from_multipart(body: bytes, boundary: str) -> str:
    """Извлечь _csrf_token из сырого multipart-тела без парсинга всего form-data.

    Ищем часть вида:
    --boundary\r\n
    Content-Disposition: form-data; name="_csrf_token"\r\n
    \r\n
    токен\r\n
    """
    pattern = (
        b"--" + boundary.encode() + b"\r\n"
        rb"Content-Disposition: form-data; name=\"_csrf_token\".*?\r\n"
        rb"\r\n"
        rb"(.*?)\r\n"
    )
    match = re.search(pattern, body, re.DOTALL)
    if match:
        return match.group(1).decode("utf-8", errors="replace").strip()
    return ""


SKIP_CSRF_PATHS = {"/api/nutrition/macros"}


async def csrf_middleware(request: Request, call_next):
    """Проверить CSRF-токен на POST/PUT/DELETE запросах (stateless)."""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        if request.url.path in SKIP_CSRF_PATHS:
            return await call_next(request)
        ct = request.headers.get("content-type", "")
        if "application/json" not in ct and not _is_disabled():
            token = ""
            if "application/x-www-form-urlencoded" in ct:
                body = await request.body()
                parsed = parse_qs(body.decode("utf-8", errors="replace"))
                token = parsed.get("_csrf_token", [""])[0]
            elif "multipart/form-data" in ct:
                body = await request.body()
                boundary = ct.split("boundary=", 1)[-1].strip().strip('"')
                if boundary:
                    token = _extract_csrf_from_multipart(body, boundary)
            if not token:
                token = request.headers.get("X-CSRF-Token", "")
            if not _validate_csrf(token):
                raise HTTPException(status_code=403, detail="CSRF-токен недействителен")
    return await call_next(request)


def _is_disabled() -> bool:
    return os.getenv("CSRF_DISABLE") == "1"
