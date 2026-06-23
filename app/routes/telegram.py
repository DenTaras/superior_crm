"""Маршруты: Telegram-бот (webhook)."""

import os
import logging

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, JSONResponse

from app.telegram_bot import get_dispatcher, get_bot

_log = logging.getLogger("superior.telegram")

router = APIRouter()

# Глобальный dispatcher (создаётся один раз)
_dispatcher = None


def _get_dp():
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = get_dispatcher()
    return _dispatcher


@router.post("/tg-webhook")
async def telegram_webhook(request: Request):
    """Обработчик входящих обновлений от Telegram."""
    bot = get_bot()
    if not bot:
        return PlainTextResponse("bot not configured", status_code=503)

    dp = _get_dp()
    try:
        body = await request.json()
        update = await dp.feed_webhook_update(bot, body, request.headers)
        return {"ok": True}
    except Exception as ex:
        _log.error("Telegram webhook error: %s", ex)
        return JSONResponse({"ok": False, "error": str(ex)}, status_code=500)
    finally:
        await bot.session.close()


@router.get("/tg-webhook-info")
async def webhook_info():
    """Информация о текущем webhook (для отладки)."""
    bot = get_bot()
    if not bot:
        return JSONResponse({"error": "bot not configured"}, status_code=503)
    try:
        info = await bot.get_webhook_info()
        result = {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
        }
        await bot.session.close()
        return JSONResponse(result)
    except Exception as ex:
        await bot.session.close()
        return JSONResponse({"error": str(ex)}, status_code=500)
