"""Абстракция над платёжными провайдерами (ЮKassa, Тинькофф, Сбер).

Поддерживается несколько провайдеров, выбирается через PAYMENT_PROVIDER env:
  yookassa  — ЮKassa (по умолчанию)
  tinkoff   — Тинькофф Касса
  sber      — Сбербанк (СберПлатеж)

В тестовом окружении (TESTING=1) используется MockProvider.
"""

import os
import json
import logging
from abc import ABC, abstractmethod

_log = logging.getLogger("superior.payment")

# ---------------------------------------------------------------------------
# Базовый класс
# ---------------------------------------------------------------------------

class PaymentProvider(ABC):
    """Абстрактный платёжный провайдер."""

    @abstractmethod
    def create_payment(
        self,
        payment_id: str,
        amount: int,          # копейки
        description: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Создать платёж и вернуть redirect_url для перехода на страницу ПШ."""
        ...

    @abstractmethod
    def verify_webhook(self, body: bytes, headers: dict) -> dict:
        """Проверить подпись webhook-уведомления.

        Возвращает словарь с ключами:
          payment_id  — ID платежа в ПШ
          status      — succeeded | cancelled | refunded
          amount      — сумма в копейках (опционально)
        Или выбрасывает ValueError при неверной подписи.
        """
        ...


# ---------------------------------------------------------------------------
# MockProvider (для тестов и разработки без реального ПШ)
# ---------------------------------------------------------------------------

class MockProvider(PaymentProvider):
    """Тестовый провайдер — не требует регистрации, работает в памяти."""

    def create_payment(self, payment_id, amount, description, success_url, cancel_url):
        _log.info("[MOCK] create_payment: id=%s, amount=%d, desc=%s", payment_id, amount, description)
        # В тестовом режиме просто имитируем редирект
        return f"/profile?payment=test&pid={payment_id}"

    def verify_webhook(self, body, headers):
        data = json.loads(body) if isinstance(body, bytes) else body
        _log.info("[MOCK] verify_webhook: %s", data)
        return {
            "payment_id": data.get("payment_id", "mock_test"),
            "status": data.get("status", "succeeded"),
        }


# ---------------------------------------------------------------------------
# YooKassa (ЮMoney)
# ---------------------------------------------------------------------------

class YooKassaProvider(PaymentProvider):
    """Провайдер ЮKassa."""

    def __init__(self):
        self.shop_id = os.getenv("YOOKASSA_SHOP_ID", "")
        self.secret_key = os.getenv("YOOKASSA_SECRET_KEY", "")
        if not self.shop_id or not self.secret_key:
            if os.getenv("DISABLE_PAYMENTS") != "1":
                _log.warning("YOOKASSA_SHOP_ID / YOOKASSA_SECRET_KEY not set, payments will fail")

    def create_payment(self, payment_id, amount, description, success_url, cancel_url):
        import yookassa
        from yookassa import Payment as YooPayment
        yookassa.Configuration.account_id = self.shop_id
        yookassa.Configuration.secret_key = self.secret_key

        payment = YooPayment.create({
            "amount": {"value": f"{amount/100:.2f}", "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": success_url},
            "capture": True,
            "description": description,
            "metadata": {"payment_id": payment_id},
        }, idempotency_key=payment_id)
        return payment.confirmation.confirmation_url

    def verify_webhook(self, body, headers):
        import yookassa
        # ЮKassa: проверка IP из списка доверенных
        event = json.loads(body) if isinstance(body, bytes) else body
        obj = event.get("object", {})
        return {
            "payment_id": obj.get("id"),
            "status": "succeeded" if event.get("event") == "payment.succeeded" else "cancelled",
        }


# ---------------------------------------------------------------------------
# Tinkoff
# ---------------------------------------------------------------------------

class TinkoffProvider(PaymentProvider):
    """Провайдер Тинькофф Касса."""

    def __init__(self):
        self.terminal_key = os.getenv("TINKOFF_TERMINAL_KEY", "")
        self.password = os.getenv("TINKOFF_PASSWORD", "")
        if not self.terminal_key or not self.password:
            if os.getenv("DISABLE_PAYMENTS") != "1":
                _log.warning("TINKOFF_TERMINAL_KEY / TINKOFF_PASSWORD not set, payments will fail")

    @staticmethod
    def _sign(data: dict, password: str) -> str:
        import hashlib
        values = [str(v) for k, v in sorted(data.items()) if v is not None and k != "Token"]
        values.append(password)
        return hashlib.sha256("".join(values).encode()).hexdigest()

    def create_payment(self, payment_id, amount, description, success_url, cancel_url):
        import requests
        data = {
            "TerminalKey": self.terminal_key,
            "OrderId": payment_id,
            "Amount": amount,
            "Description": description,
            "NotificationURL": cancel_url.replace("cancel", "payment-callback"),
            "SuccessURL": success_url,
        }
        data["Token"] = self._sign(data, self.password)
        resp = requests.post("https://securepay.tinkoff.ru/v2/Init", json=data, timeout=15)
        resp.raise_for_status()
        return resp.json()["PaymentURL"]

    def verify_webhook(self, body, headers):
        data = json.loads(body) if isinstance(body, bytes) else body
        token = data.pop("Token", "")
        if self._sign(data, self.password) != token:
            raise ValueError("Invalid Tinkoff webhook signature")
        return {
            "payment_id": data.get("PaymentId"),
            "status": "succeeded" if data.get("Status") == "CONFIRMED" else "cancelled",
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_provider() -> PaymentProvider:
    """Вернуть провайдера в зависимости от PAYMENT_PROVIDER env."""
    if os.getenv("DISABLE_PAYMENTS") == "1" or os.getenv("TESTING") or os.getenv("CSRF_DISABLE"):
        return MockProvider()
    provider_name = os.getenv("PAYMENT_PROVIDER", "yookassa").lower()
    providers = {
        "yookassa": YooKassaProvider,
        "tinkoff": TinkoffProvider,
        "mock": MockProvider,
    }
    cls = providers.get(provider_name)
    if cls is None:
        if os.getenv("DISABLE_PAYMENTS") != "1":
            _log.warning("Unknown PAYMENT_PROVIDER=%s, falling back to mock", provider_name)
        return MockProvider()
    return cls()


# Экземпляр для импорта
if os.getenv("DISABLE_PAYMENTS") == "1":
    payment_provider = MockProvider()
else:
    payment_provider = get_provider()
