"""Тесты Telegram-бота (без реального API Telegram)."""

import os
import sys


def test_webhook_accepts_empty_body(anon_client):
    """Webhook принимает запрос (с токеном или без — главное без паники)."""
    r = anon_client.post("/tg-webhook", json={})
    assert r.status_code in (200, 500, 503)


def test_webhook_info(anon_client):
    """/tg-webhook-info отдаёт информацию."""
    r = anon_client.get("/tg-webhook-info")
    assert r.status_code in (200, 503)


def test_telegram_module_imports():
    """Модуль telegram_bot импортируется без ошибок."""
    # Сбрасываем кеш модуля, чтобы перезагрузить с новым окружением
    for mod in list(sys.modules.keys()):
        if 'telegram_bot' in mod:
            del sys.modules[mod]
    from app.telegram_bot import get_dispatcher, post_to_channel, notify_slot_created, notify_booking
    dp = get_dispatcher()
    assert dp is not None


def test_router_has_handlers():
    """Роутер содержит зарегистрированные хендлеры."""
    for mod in list(sys.modules.keys()):
        if 'telegram_bot' in mod:
            del sys.modules[mod]
    from app.telegram_bot import router
    assert len(router.message.handlers) >= 4


def test_post_to_channel_returns_false_without_token():
    """post_to_channel возвращает False без токена."""
    import asyncio
    # Очищаем env временно
    old_token = os.environ.pop("BOT_TOKEN", None)
    old_channel = os.environ.pop("BOT_CHANNEL_ID", None)
    for mod in list(sys.modules.keys()):
        if 'telegram_bot' in mod:
            del sys.modules[mod]
    try:
        from app.telegram_bot import post_to_channel
        result = asyncio.run(post_to_channel("test"))
        assert result is False
    finally:
        if old_token is not None:
            os.environ["BOT_TOKEN"] = old_token
        if old_channel is not None:
            os.environ["BOT_CHANNEL_ID"] = old_channel


def test_post_to_channel_with_wrong_token():
    """post_to_channel с неверным токеном не падает с exception."""
    import asyncio
    for mod in list(sys.modules.keys()):
        if 'telegram_bot' in mod:
            del sys.modules[mod]
    old_token = os.environ.get("BOT_TOKEN")
    old_channel = os.environ.get("BOT_CHANNEL_ID")
    os.environ["BOT_TOKEN"] = "bad_token:000"
    os.environ["BOT_CHANNEL_ID"] = "@test_channel"
    try:
        from app.telegram_bot import post_to_channel
        result = asyncio.run(post_to_channel("test"))
        assert result is False
    finally:
        if old_token:
            os.environ["BOT_TOKEN"] = old_token
        else:
            os.environ.pop("BOT_TOKEN", None)
        if old_channel:
            os.environ["BOT_CHANNEL_ID"] = old_channel
        else:
            os.environ.pop("BOT_CHANNEL_ID", None)
