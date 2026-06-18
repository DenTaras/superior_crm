"""Тесты логирования: проверяем, что audit_log и request-логгер работают."""

from datetime import datetime, timedelta

from app.logging_config import audit_log


def test_audit_log_function(caplog):
    """Проверка вызова audit_log: сообщение появляется в логах."""
    caplog.set_level(10)  # ALL
    audit_log("superior.audit.test", "TEST_ACTION", client_id=42, note="hello")
    assert len(caplog.records) >= 1
    assert any("[TEST_ACTION]" in r.message for r in caplog.records)
    assert any("client_id=42" in r.message for r in caplog.records)
    assert any("note=hello" in r.message for r in caplog.records)


def test_audit_client_create(client, db_session, caplog):
    """Создание клиента порождает audit-запись."""
    caplog.set_level(10)
    from app.models import Client

    r = client.post("/clients/create", data={
        "first_name": "Log", "last_name": "Test",
        "phone": "+70000000120",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert any("[CREATE]" in r.message and "client_id=" in r.message
               for r in caplog.records), "Нет audit-записи CREATE"


def test_audit_client_delete(client, db_session, caplog):
    """Удаление клиента порождает audit-запись."""
    caplog.set_level(10)
    from app.models import Client

    c = Client(first_name="Del", last_name="LogTest", phone="+70000000121")
    db_session.add(c)
    db_session.commit()
    cid = c.id

    r = client.post(f"/clients/delete/{cid}", follow_redirects=False)
    assert r.status_code == 303
    assert any("[DELETE]" in r.message and f"client_id={cid}" in r.message
               for r in caplog.records), "Нет audit-записи DELETE"


def test_audit_slot_create(client, db_session, caplog):
    """Создание слота порождает audit-запись."""
    caplog.set_level(10)
    # уникальное время (далеко в будущем) — избегаем конфликтов с другими тестами
    start = (datetime.now() + timedelta(days=60, hours=8)).strftime("%Y-%m-%dT%H:%M")
    r = client.post("/slots/add", data={
        "start_time": start, "capacity": 2,
    }, follow_redirects=False)
    assert r.status_code == 303
    assert "/schedule" in r.headers.get("location", ""), f"редирект не на /schedule: {r.headers.get('location')}"
    assert "flash=slot_conflict" not in r.headers.get("location", ""), "конфликт — слот не создан"
    assert any("[CREATE]" in r.message and "slot_id=" in r.message
               for r in caplog.records), f"Нет audit-записи CREATE. Логи: {[r.message for r in caplog.records]}"


def test_audit_booking_add(client, db_session, caplog):
    """Добавление брони порождает audit-запись."""
    caplog.set_level(10)
    from app.models import Client, Slot, Booking, SubscriptionPurchase

    c = Client(first_name="Book", last_name="Log", phone="+70000000122")
    s = Slot(start_time=datetime.now().replace(hour=9, minute=0) + timedelta(hours=0), capacity=4)
    db_session.add_all([c, s])
    db_session.commit()
    p = SubscriptionPurchase(client_id=c.id, time_slot="УТРО", format_name="Group", package_size=5, price=2500, remaining=5)
    db_session.add(p)
    db_session.commit()

    r = client.post(f"/slot/{s.id}/add", data={"client_id": c.id}, follow_redirects=False)
    assert r.status_code == 303
    assert any("[ADD]" in r.message and f"client_id={c.id}" in r.message
               for r in caplog.records), "Нет audit-записи ADD брони"


def test_audit_subscription_add(client, db_session, caplog):
    """Добавление абонемента порождает audit-запись."""
    caplog.set_level(10)
    from app.models import Client

    c = Client(first_name="SubLog", last_name="Test", phone="+70000000123")
    db_session.add(c)
    db_session.commit()

    r = client.post("/clients/add_subscription", data={
        "client_id": c.id, "time_slot": "УТРО", "format_name": "VIP", "package_size": "12",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert any("[ADD]" in r.message and f"client_id={c.id}" in r.message
               for r in caplog.records), "Нет audit-записи SUBSCRIPTION"
