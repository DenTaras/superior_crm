"""Тесты платёжного модуля (без роутов — они отключены)."""

import json

from app.models import Payment, SubscriptionPurchase
from app.pricing import get_price
from app.auth import hash_password


def test_mock_provider_create_payment():
    """MockProvider возвращает корректную ссылку."""
    from app.payment import MockProvider
    prov = MockProvider()
    url = prov.create_payment(
        payment_id="42", amount=500000, description="VIP УТРО 12",
        success_url="/profile?payment=success",
        cancel_url="/profile?payment=cancelled",
    )
    assert "/profile?payment=test" in url


def test_mock_provider_verify():
    """MockProvider корректно верифицирует callback."""
    from app.payment import MockProvider
    prov = MockProvider()
    data = prov.verify_webhook(
        json.dumps({"payment_id": "42", "status": "succeeded"}).encode(),
        {},
    )
    assert data["payment_id"] == "42"
    assert data["status"] == "succeeded"
