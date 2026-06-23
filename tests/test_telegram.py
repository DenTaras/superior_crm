"""Тесты Telegram-бота (без реального API Telegram)."""

import json
import os

import pytest
from fastapi.testclient import TestClient


def test_webhook_returns_503_without_token(anon_client):
    """Без BOT_TOKEN webhook возвращает 503."""
    # Убедимся, что токен не задан
    old_token = os.environ.pop("BOT_TOKEN", None)
    try:
        r = anon_client.post("/tg-webhook", json={})
        assert r.status_code == 503
        assert "bot not configured" in r.text
    finally:
        if old_token is not None:
            os.environ["BOT_TOKEN"] = old_token


def test_webhook_info_without_token(anon_client):
    """Без BOT_TOKEN /tg-webhook-info возвращает 503."""
    old_token = os.environ.pop("BOT_TOKEN", None)
    try:
        r = anon_client.get("/tg-webhook-info")
        assert r.status_code == 503
    finally:
        if old_token is not None:
            os.environ["BOT_TOKEN"] = old_token


def test_telegram_module_imports():
    """Модуль telegram_bot импортируется без ошибок."""
    from app.telegram_bot import get_dispatcher, post_to_channel, notify_slot_created, notify_booking
    dp = get_dispatcher()
    assert dp is not None


def test_router_has_handlers():
    """Роутер содержит зарегистрированные хендлеры."""
    from app.telegram_bot import router
    # Проверяем, что зарегистрированы хендлеры на сообщения
    assert len(router.message.handlers) >= 4


def test_post_to_channel_returns_false_without_token():
    """post_to_channel возвращает False без настроек."""
    import asyncio
    from app.telegram_bot import post_to_channel

    old_token = os.environ.pop("BOT_TOKEN", None)
    old_channel = os.environ.pop("BOT_CHANNEL_ID", None)
    try:
        result = asyncio.run(post_to_channel("test"))
        assert result is False
    finally:
        if old_token is not None:
            os.environ["BOT_TOKEN"] = old_token
        if old_channel is not None:
            os.environ["BOT_CHANNEL_ID"] = old_channel


def test_post_to_channel_with_wrong_token():
    """post_to_channel с неверным токеном не падает."""
    import asyncio
    from app.telegram_bot import post_to_channel

    old_token = os.environ.get("BOT_TOKEN")
    old_channel = os.environ.get("BOT_CHANNEL_ID")
    os.environ["BOT_TOKEN"] = "bad_token:000"
    os.environ["BOT_CHANNEL_ID"] = "@test_channel"
    try:
        result = asyncio.run(post_to_channel("test"))
        assert result is False  # ожидаемо не доставится, но без exception
    finally:
        if old_token:
            os.environ["BOT_TOKEN"] = old_token
        else:
            del os.environ["BOT_TOKEN"]
        if old_channel:
            os.environ["BOT_CHANNEL_ID"] = old_channel
        else:
            del os.environ["BOT_CHANNEL_ID"]
