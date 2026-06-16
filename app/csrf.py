"""CSRF-защита: токен в сессии, проверка на POST-запросах."""

import secrets
from urllib.parse import parse_qs

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


def get_csrf_token(request: Request) -> str:
    """Получить или создать CSRF-токен в сессии."""
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_hex(32)
        request.session["csrf_token"] = token
    return token


def csrf_input(request: Request) -> str:
    """HTML скрытого поля с CSRF-токеном для вставки в формы."""
    token = get_csrf_token(request)
    return f'<input type="hidden" name="_csrf_token" value="{token}" />'


class CsrfMiddleware(BaseHTTPMiddleware):
    """Middleware: проверяет CSRF-токен на POST/PUT/DELETE запросах.

    Токен ищется в:
    1. Поле формы `_csrf_token`
    2. Заголовке `X-CSRF-Token`

    JSON-запросы пропускаются без проверки.
    Отключается переменной окружения CSRF_DISABLE=1 (только для тестов).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            ct = request.headers.get("content-type", "")
            if "application/json" not in ct and not _is_disabled():
                token = ""
                if "application/x-www-form-urlencoded" in ct:
                    body = await request.body()
                    parsed = parse_qs(body.decode("utf-8", errors="replace"))
                    token = parsed.get("_csrf_token", [""])[0]
                if not token:
                    token = request.headers.get("X-CSRF-Token", "")
                if not _validate_csrf(request, token):
                    raise HTTPException(status_code=403, detail="CSRF-токен недействителен")
        return await call_next(request)


def _validate_csrf(request: Request, token: str) -> bool:
    expected = request.session.get("csrf_token")
    if not expected or not secrets.compare_digest(expected, token):
        return False
    return True


def _is_disabled() -> bool:
    import os
    return os.getenv("CSRF_DISABLE") == "1"
