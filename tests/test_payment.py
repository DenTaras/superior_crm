"""Тесты онлайн-оплаты (mock-провайдер)."""

import json

from app.models import Payment, SubscriptionPurchase, Client
from app.pricing import get_price
from app.auth import hash_password


def test_create_payment_requires_auth(anon_client):
    """Неавторизованный получает редирект на login."""
    r = anon_client.post("/api/create-payment", data={
        "time_slot": "УТРО", "format_name": "VIP", "package_size": 4,
    }, follow_redirects=False)
    assert r.status_code == 303


def test_create_payment_requires_client(anon_client, db_session):
    """Авторизованный админ не может создать платёж (только client)."""
    r = anon_client.post("/login", data={"login": "admin", "password": "admin"},
                         follow_redirects=False)
    assert r.status_code == 303
    r2 = anon_client.post("/api/create-payment", data={
        "time_slot": "УТРО", "format_name": "VIP", "package_size": 4,
    }, follow_redirects=False)
    assert r2.status_code == 303  # редирект на / (нет прав)


def test_create_payment_success(anon_client, db_session):
    """Клиент создаёт платёж, получает redirect_url."""
    cl = Client(first_name="PayTest", login="pay_user_1",
                password_hash=hash_password("pass"))
    db_session.add(cl)
    db_session.commit()

    r = anon_client.post("/login", data={"login": "pay_user_1", "password": "pass"},
                         follow_redirects=False)
    assert r.status_code == 303

    r2 = anon_client.post("/api/create-payment", data={
        "time_slot": "УТРО", "format_name": "VIP", "package_size": 4,
    })
    assert r2.status_code == 200
    data = r2.json()
    assert "redirect_url" in data
    assert "/profile?payment=" in data["redirect_url"]


def test_create_payment_invalid_combo(anon_client, db_session):
    """Неверная комбинация -> ошибка 400."""
    cl = Client(first_name="PayTest2", login="pay_user_2",
                password_hash=hash_password("pass"))
    db_session.add(cl)
    db_session.commit()

    anon_client.post("/login", data={"login": "pay_user_2", "password": "pass"},
                     follow_redirects=False)

    r = anon_client.post("/api/create-payment", data={
        "time_slot": "НОЧЬ", "format_name": "XXX", "package_size": 99,
    })
    assert r.status_code == 400
    assert "error" in r.json()


def test_payment_created_in_db(anon_client, db_session):
    """После создания платежа в БД появляется запись Payment."""
    cl = Client(first_name="PayTest3", login="pay_user_3",
                password_hash=hash_password("pass"))
    db_session.add(cl)
    db_session.commit()

    anon_client.post("/login", data={"login": "pay_user_3", "password": "pass"},
                     follow_redirects=False)

    r = anon_client.post("/api/create-payment", data={
        "time_slot": "ДЕНЬ", "format_name": "Double", "package_size": 8,
    })
    assert r.status_code == 200

    payments = db_session.query(Payment).filter_by(client_id=cl.id).all()
    assert len(payments) == 1
    p = payments[0]
    assert p.client_id == cl.id
    assert p.amount == get_price("ДЕНЬ", "Double", 8) * 100
    assert p.status == "pending"
    assert p.description == "Double ДЕНЬ 8"


def test_payment_callback_success(anon_client, db_session):
    """Webhook подтверждает платёж и создаёт SubscriptionPurchase."""
    cl = Client(first_name="PayTest4", login="pay_user_4",
                password_hash=hash_password("pass"))
    db_session.add(cl)
    db_session.commit()

    anon_client.post("/login", data={"login": "pay_user_4", "password": "pass"},
                     follow_redirects=False)

    anon_client.post("/api/create-payment", data={
        "time_slot": "ВЕЧЕР", "format_name": "Group", "package_size": 12,
    })
    payment = db_session.query(Payment).filter_by(client_id=cl.id).first()
    assert payment is not None, "Payment not found for this client"

    # Симулируем callback от ПШ
    callback_data = {
        "payment_id": str(payment.id),
        "status": "succeeded",
        "amount": payment.amount,
    }
    r = anon_client.post("/api/payment-callback", json=callback_data)
    assert r.status_code == 200

    db_session.refresh(payment)
    assert payment.status == "succeeded"
    assert payment.confirmed_at is not None

    purchases = db_session.query(SubscriptionPurchase).filter_by(
        client_id=cl.id
    ).all()
    assert len(purchases) == 1
    sp = purchases[0]
    assert sp.time_slot == "ВЕЧЕР"
    assert sp.format_name == "Group"
    assert sp.package_size == 12
    assert sp.remaining == 12
    assert sp.price == payment.amount // 100


def test_payment_callback_idempotent(anon_client, db_session):
    """Повторный callback не создаёт дубликат SubscriptionPurchase."""
    cl = Client(first_name="PayTest5", login="pay_user_5",
                password_hash=hash_password("pass"))
    db_session.add(cl)
    db_session.commit()

    anon_client.post("/login", data={"login": "pay_user_5", "password": "pass"},
                     follow_redirects=False)
    anon_client.post("/api/create-payment", data={
        "time_slot": "УТРО", "format_name": "VIP", "package_size": 4,
    })
    payment = db_session.query(Payment).filter_by(client_id=cl.id).first()
    assert payment is not None
    callback = {"payment_id": str(payment.id), "status": "succeeded"}

    r1 = anon_client.post("/api/payment-callback", json=callback)
    assert r1.status_code == 200

    r2 = anon_client.post("/api/payment-callback", json=callback)
    assert r2.status_code == 200

    purchases = db_session.query(SubscriptionPurchase).filter_by(
        client_id=cl.id
    ).all()
    assert len(purchases) == 1


def test_payment_callback_cancelled(anon_client, db_session):
    """Callback со статусом cancelled не создаёт абонемент."""
    cl = Client(first_name="PayTest6", login="pay_user_6",
                password_hash=hash_password("pass"))
    db_session.add(cl)
    db_session.commit()

    anon_client.post("/login", data={"login": "pay_user_6", "password": "pass"},
                     follow_redirects=False)
    anon_client.post("/api/create-payment", data={
        "time_slot": "УТРО", "format_name": "VIP", "package_size": 4,
    })
    payment = db_session.query(Payment).filter_by(client_id=cl.id).first()
    assert payment is not None

    r = anon_client.post("/api/payment-callback", json={
        "payment_id": str(payment.id), "status": "cancelled",
    })
    assert r.status_code == 200

    db_session.refresh(payment)
    assert payment.status == "cancelled"

    purchases = db_session.query(SubscriptionPurchase).filter_by(
        client_id=cl.id
    ).all()
    assert len(purchases) == 0


def test_payment_status_endpoint(anon_client, db_session):
    """GET /api/payment-status возвращает статус платежа."""
    cl = Client(first_name="PayTest7", login="pay_user_7",
                password_hash=hash_password("pass"))
    db_session.add(cl)
    db_session.commit()

    anon_client.post("/login", data={"login": "pay_user_7", "password": "pass"},
                     follow_redirects=False)
    anon_client.post("/api/create-payment", data={
        "time_slot": "УТРО", "format_name": "VIP", "package_size": 4,
    })
    payment = db_session.query(Payment).filter_by(client_id=cl.id).first()
    assert payment is not None

    r = anon_client.get(f"/api/payment-status/{payment.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "pending"
    assert data["amount"] == payment.amount


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
