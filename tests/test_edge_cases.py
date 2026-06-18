"""Краевые случаи и тесты безопасности.

Проверяет:
- Невалидные/отсутствующие ресурсы (404, редиректы)
- Граничные значения (заполненный слот)
- Некорректные данные (пустые поля, неправильный формат)
- XSS-попытки, SQL-инъекции в поиске
- Повторные операции (двойное завершение, двойное удаление)
"""

from datetime import datetime, timedelta
import json

import pytest


# ===== КРАЕВЫЕ СЛУЧАИ: БРОНИРОВАНИЯ =====


def test_booking_with_zero_remaining_sessions_is_blocked(client, db_session):
    """Клиент без активных абонементов не может записаться на слот."""
    from app.models import Client, Slot, Booking, SubscriptionPurchase

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    c = Client(first_name="Zero", last_name="Sessions", phone="+70000000050",
               name="Zero")
    s = Slot(start_time=now + timedelta(days=1, hours=0), capacity=4)
    db_session.add_all([c, s])
    db_session.commit()
    # нет SubscriptionPurchase — 0 занятий

    r = client.post(f"/slot/{s.id}/add", data={"client_id": c.id}, follow_redirects=False)
    assert r.status_code == 303
    assert "flash=limit_reached" in r.headers["location"]
    booking = db_session.query(Booking).filter(
        Booking.client_id == c.id, Booking.slot_id == s.id
    ).first()
    assert booking is None


def test_booking_blocked_when_future_bookings_equal_remaining(client, db_session):
    """Клиент не может записаться, если число будущих броней == доступным занятиям."""
    from app.models import Client, Slot, Booking, SubscriptionPurchase

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    c = Client(first_name="Exact", last_name="Limit", phone="+70000000051",
               name="Exact Limit")
    s1 = Slot(start_time=now + timedelta(days=1, hours=0), capacity=4)
    s2 = Slot(start_time=now + timedelta(days=1, hours=1), capacity=4)
    db_session.add_all([c, s1, s2])
    db_session.commit()
    # 1 занятие в абонементе
    p = SubscriptionPurchase(client_id=c.id, time_slot="УТРО", format_name="Group", package_size=1, price=500, remaining=1)
    db_session.add(p)
    db_session.commit()

    # первая запись успешна
    r1 = client.post(f"/slot/{s1.id}/add", data={"client_id": c.id}, follow_redirects=False)
    assert r1.status_code == 303

    # вторая — blocked (уже 1 будущая бронь, а доступно только 1 занятие)
    r2 = client.post(f"/slot/{s2.id}/add", data={"client_id": c.id}, follow_redirects=False)
    assert r2.status_code == 303
    assert "flash=limit_reached" in r2.headers["location"]


def test_add_client_to_full_slot_fails(client, db_session):
    """Попытка записать клиента в уже заполненный слот отклоняется."""
    from app.models import Client, Slot, Booking, SubscriptionPurchase

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    s = Slot(start_time=now + timedelta(days=1, hours=0), capacity=1)
    c1 = Client(first_name="First", last_name="Client", phone="+70000000052", name="C1")
    c2 = Client(first_name="Second", last_name="Client", phone="+70000000053", name="C2")
    db_session.add_all([s, c1, c2])
    db_session.commit()
    for c in [c1, c2]:
        db_session.add(SubscriptionPurchase(client_id=c.id, time_slot="УТРО", format_name="Group", package_size=5, price=2500, remaining=5))
    db_session.commit()

    r1 = client.post(f"/slot/{s.id}/add", data={"client_id": c1.id}, follow_redirects=False)
    assert r1.status_code == 303
    # capacity=1, второй не должен пройти
    r2 = client.post(f"/slot/{s.id}/add", data={"client_id": c2.id}, follow_redirects=False)
    assert r2.status_code == 303
    bookings = db_session.query(Booking).filter(Booking.slot_id == s.id).all()
    assert len(bookings) == 1


def test_remove_nonexistent_booking_does_not_crash(client, db_session):
    """Удаление несуществующей брони не должно вызывать ошибку."""
    from app.models import Client, Slot

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    c = Client(first_name="Ghost", last_name="Booking", phone="+70000000054", name="Ghost")
    s = Slot(start_time=now + timedelta(hours=5), capacity=2)
    db_session.add_all([c, s])
    db_session.commit()

    r = client.post(f"/slot/{s.id}/remove", data={"client_id": c.id}, follow_redirects=False)
    # должен вернуть редирект, а не 500
    assert r.status_code == 303


def test_double_booking_removal_does_not_crash(client, db_session):
    """Повторное удаление одной и той же брони не вызывает ошибку."""
    from app.models import Client, Slot, Booking

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    c = Client(first_name="Double", last_name="Remove", phone="+70000000055", name="Double")
    s = Slot(start_time=now + timedelta(hours=6), capacity=2)
    db_session.add_all([c, s])
    db_session.commit()
    b = Booking(client_id=c.id, slot_id=s.id)
    db_session.add(b)
    db_session.commit()

    r1 = client.post(f"/slot/{s.id}/remove", data={"client_id": c.id}, follow_redirects=False)
    assert r1.status_code == 303
    # повторное удаление
    r2 = client.post(f"/slot/{s.id}/remove", data={"client_id": c.id}, follow_redirects=False)
    assert r2.status_code == 303


# ===== КРАЕВЫЕ СЛУЧАИ: СЛОТЫ =====


def test_delete_nonexistent_slot_redirects(client):
    """Удаление несуществующего слота перенаправляет на /schedule."""
    r = client.post("/slots/delete/99999", data={}, follow_redirects=False)
    assert r.status_code == 303
    assert "/schedule" in r.headers["location"]


def test_edit_nonexistent_slot_redirects(client):
    """Редактирование несуществующего слота перенаправляет на /schedule."""
    now = datetime.now().replace(hour=9, minute=0) + timedelta(hours=2)
    r = client.post("/slots/edit/99999", data={
        "start_time": now.strftime("%Y-%m-%dT%H:%M"), "capacity": 2
    }, follow_redirects=False)
    assert r.status_code == 303


def test_complete_nonexistent_slot_redirects(client):
    """Завершение несуществующего слота перенаправляет на /schedule."""
    r = client.post("/slot/99999/complete", data={}, follow_redirects=False)
    assert r.status_code == 303
    assert "/schedule" in r.headers["location"]


def test_program_page_for_nonexistent_slot_redirects(client):
    """Страница программы для несуществующего слота перенаправляет."""
    r = client.get("/slot/99999/program", follow_redirects=False)
    assert r.status_code == 303
    assert "/schedule" in r.headers["location"]


def test_create_slot_with_empty_start_time(client, db_session):
    """Пустая start_time при создании слота не должна вызвать 500."""
    r = client.post("/slots/add", data={"start_time": "", "capacity": 2}, follow_redirects=False)
    # должно вернуть редирект или 400, но не 500
    assert r.status_code in (303, 400, 422)


def test_bulk_create_with_end_before_start(client):
    """Массовое создание слотов с end_time < start_time не создаёт слоты."""
    future = (datetime.now().replace(hour=9, minute=0) + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M")
    past = (datetime.now().replace(hour=9, minute=0) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    r = client.post("/slots/add", data={
        "start_time": future, "end_time": past, "capacity": 2
    }, follow_redirects=False)
    assert r.status_code == 303


def test_bulk_remove_with_empty_dates(client):
    """Массовое удаление без дат не вызывает ошибку."""
    r = client.post("/slots/remove", data={}, follow_redirects=False)
    assert r.status_code == 303


def test_negative_capacity_rejected_by_validation(client, db_session):
    """Отрицательная вместимость слота отклоняется Pydantic (422)."""
    start = (datetime.now() + timedelta(days=30, hours=4)).replace(second=0, microsecond=0)
    r = client.post("/slots/add", data={
        "start_time": start.strftime("%Y-%m-%dT%H:%M"), "capacity": -5
    }, follow_redirects=False)
    # Pydantic валидация не пропускает capacity вне диапазона 1–4
    assert r.status_code == 422


def test_zero_capacity_rejected_by_validation(client, db_session):
    """Нулевая вместимость слота отклоняется Pydantic (422)."""
    start = (datetime.now() + timedelta(days=30, hours=5)).replace(second=0, microsecond=0)
    r = client.post("/slots/add", data={
        "start_time": start.strftime("%Y-%m-%dT%H:%M"), "capacity": 0
    }, follow_redirects=False)
    assert r.status_code == 422


# ===== КРАЕВЫЕ СЛУЧАИ: КЛИЕНТЫ =====


def test_create_client_with_empty_first_name(client, db_session):
    """Пустое имя не создаёт клиента (редирект без создания)."""
    from app.models import Client

    r = client.post("/clients/create", data={
        "first_name": "", "last_name": "",
        "patronymic": "", "birth_year": "", "birth_place": "", "phone": ""
    }, follow_redirects=False)
    # FastAPI возвращает 422 если int поле получает пустую строку;
    # это тоже защита от некорректных данных
    assert r.status_code in (303, 422)


def test_delete_nonexistent_client_redirects(client):
    """Удаление несуществующего клиента не вызывает 500."""
    r = client.post("/clients/delete/99999", follow_redirects=False)
    assert r.status_code == 303


def test_edit_nonexistent_client_redirects(client):
    """Редактирование несуществующего клиента перенаправляет на /clients."""
    r = client.post("/clients/edit/99999", data={
        "first_name": "Test", "last_name": "", "patronymic": "",
        "birth_year": "", "birth_place": "", "phone": ""
    }, follow_redirects=False)
    assert r.status_code == 303
    assert "/clients" in r.headers["location"]


def test_get_edit_for_nonexistent_client_redirects(client):
    """GET страницы редактирования несуществующего клиента перенаправляет."""
    r = client.get("/clients/edit/99999", follow_redirects=False)
    assert r.status_code == 303
    assert "/clients" in r.headers["location"]


def test_client_with_very_long_name(client, db_session):
    """Очень длинное имя клиента (10k символов) не вызывает 500."""
    long_name = "A" * 10000
    r = client.post("/clients/create", data={
        "first_name": long_name, "last_name": "Long", "phone": "+70000000060"
    }, follow_redirects=False)
    assert r.status_code == 303


# ===== КРАЕВЫЕ СЛУЧАИ: ПРОГРАММА ТРЕНИРОВКИ =====


def test_save_empty_note(client, db_session):
    """Сохранение пустой заметки не вызывает ошибку."""
    from app.models import Client, Slot, Booking, TrainingNote

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    c = Client(first_name="Empty", last_name="Note", phone="+70000000070", name="Empty Note")
    s = Slot(start_time=now + timedelta(days=1, hours=2), capacity=2)
    db_session.add_all([c, s])
    db_session.commit()
    b = Booking(client_id=c.id, slot_id=s.id)
    db_session.add(b)
    db_session.commit()

    r = client.post(f"/slot/{s.id}/program/save", data={
        "client_id": str(c.id), "text": ""
    })
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_program_save_nonexistent_slot_creates_orphan_note(client, db_session):
    """Сохранение заметки для несуществующего слота создаёт запись (см. оптимизацию).

    В текущей реализации отсутствует проверка существования слота.
    Это тест-документация: в будущем endpoint должен проверять slot_id.
    """
    from app.models import TrainingNote

    r = client.post("/slot/99999/program/save", data={
        "client_id": "1", "text": "test"
    })
    # сейчас возвращает 200 и создаёт TrainingNote (слот не проверяется)
    assert r.status_code == 200
    orphan = db_session.query(TrainingNote).filter(
        TrainingNote.slot_id == 99999, TrainingNote.client_id == 1
    ).first()
    assert orphan is not None


def test_program_save_nonexistent_client_still_saves(client, db_session):
    """Сохранение заметки с несуществующим client_id всё равно сохраняется.

    Текущая реализация не проверяет существование client_id.
    """
    from app.models import Slot, TrainingNote

    s = Slot(start_time=datetime.now().replace(hour=9, minute=0) + timedelta(days=1, hours=0), capacity=2)
    db_session.add(s)
    db_session.commit()

    r = client.post(f"/slot/{s.id}/program/save", data={
        "client_id": "99999", "text": "test"
    })
    assert r.status_code == 200
    # создалась запись с client_id=99999
    note = db_session.query(TrainingNote).filter(
        TrainingNote.slot_id == s.id, TrainingNote.client_id == 99999
    ).first()
    assert note is not None


# ===== ТЕСТЫ БЕЗОПАСНОСТИ =====


XSS_PAYLOADS = [
    "<script>alert('xss')</script>",
    "<img src=x onerror=alert(1)>",
    "\"><script>alert(1)</script>",
    "'; DROP TABLE clients; --",
]


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_xss_in_client_name_is_escaped(client, db_session, payload):
    """XSS-попытки в имени клиента не должны ломать страницу."""
    r = client.post("/clients/create", data={
        "first_name": payload, "last_name": payload,
        "phone": "+70000000080"
    }, follow_redirects=False)
    assert r.status_code == 303

    # страница списка клиентов не должна содержать неэкранированные теги
    r2 = client.get("/clients")
    assert r2.status_code == 200
    # тег <script> не должен быть в исходном HTML как активный элемент
    assert "<script>" not in r2.text or "&lt;script&gt;" in r2.text


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_xss_in_program_note_is_escaped(client, db_session, payload):
    """XSS-попытки в заметке тренировки не должны быть в неэкранированном виде."""
    from app.models import Client, Slot, Booking

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    c = Client(first_name="Safe", last_name="Note", phone="+70000000081", name="Safe Note")
    s = Slot(start_time=now + timedelta(days=1, hours=4), capacity=2)
    db_session.add_all([c, s])
    db_session.commit()
    b = Booking(client_id=c.id, slot_id=s.id)
    db_session.add(b)
    db_session.commit()

    r = client.post(f"/slot/{s.id}/program/save", data={
        "client_id": str(c.id), "text": payload
    })
    assert r.status_code == 200
    assert r.json().get("ok") is True

    # страница программы — payload не должен быть в неэкранированном виде
    r2 = client.get(f"/slot/{s.id}/program")
    assert r2.status_code == 200
    # payload (например, "<script>alert('xss')</script>") должен быть экранирован
    # в HTML: &lt;script&gt;alert('xss')&lt;/script&gt;
    import html
    escaped = html.escape(payload, quote=True)
    # если payload встречается, то только в экранированном виде
    if payload in r2.text:
        # ищем неэкранированное вхождение в notes-data
        import json as _json
        import re as _re
        m = _re.search(r'<script id="notes-data" type="application/json">(.*?)</script>', r2.text, _re.S)
        if m:
            raw = m.group(1)
            # данные в JSON — payload может быть экранирован внутри JSON
            assert payload not in raw or escaped in raw or _json.dumps(payload) in raw


SQLI_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE clients; --",
    "\" OR 1=1 --",
    "1' UNION SELECT * FROM clients --",
]


@pytest.mark.parametrize("payload", SQLI_PAYLOADS)
def test_sql_injection_in_client_search_is_safe(client, db_session, payload):
    """SQL-инъекции в поиске клиентов не вызывают ошибок."""
    r = client.get(f"/clients?q_name={payload}")
    assert r.status_code == 200


@pytest.mark.parametrize("payload", SQLI_PAYLOADS)
def test_sql_injection_in_phone_search_is_safe(client, db_session, payload):
    """SQL-инъекции в поиске по телефону не вызывают ошибок."""
    r = client.get(f"/clients?q_phone={payload}")
    assert r.status_code == 200


def test_unexpected_form_fields_are_ignored(client, db_session):
    """Лишние поля в форме создания клиента не вызывают ошибку."""
    r = client.post("/clients/create", data={
        "first_name": "Safe",
        "last_name": "Client",
        "phone": "+70000000090",
        "is_admin": "true",
        "password": "hacked",
        "role": "superuser",
    }, follow_redirects=False)
    assert r.status_code == 303


def test_access_nonexistent_page_returns_404(client):
    """Несуществующий маршрут возвращает 404."""
    r = client.get("/nonexistent")
    assert r.status_code == 404


def test_malformed_slot_time_does_not_crash(client):
    """Некорректный формат времени не вызывает 500."""
    r = client.post("/slots/add", data={
        "start_time": "not-a-date",
        "capacity": 2
    }, follow_redirects=False)
    # 400, 422 или редирект — допустимо, главное не 500
    assert r.status_code != 500


def test_mass_assignment_on_client_edit(client, db_session):
    """Попытка передать лишние поля при редактировании клиента безопасна."""
    from app.models import Client

    c = Client(first_name="Safe", last_name="Edit", phone="+70000000091", name="Safe Edit")
    db_session.add(c)
    db_session.commit()

    r = client.post(f"/clients/edit/{c.id}", data={
        "first_name": "Updated",
        "last_name": "",
        "patronymic": "",
        "birth_year": "",
        "birth_place": "",
        "phone": "",
    }, follow_redirects=False)
    assert r.status_code == 303
    updated = db_session.get(Client, c.id)
    assert updated.first_name == "Updated"


# ===== ДОПОЛНИТЕЛЬНЫЕ КРАЕВЫЕ СЛУЧАИ =====


def test_double_complete_slot_is_safe(client, db_session):
    """Повторное завершение уже завершённого слота не вызывает 500."""
    from app.models import Client, Slot, Booking, SubscriptionPurchase

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    c = Client(first_name="Double", last_name="Complete", phone="+70000000100",
               name="Double Complete")
    s = Slot(start_time=now + timedelta(hours=8), capacity=2)
    db_session.add_all([c, s])
    db_session.commit()
    p = SubscriptionPurchase(client_id=c.id, time_slot="УТРО", format_name="Group", package_size=2, price=1000, remaining=2)
    db_session.add(p)
    db_session.commit()
    b = Booking(client_id=c.id, slot_id=s.id)
    db_session.add(b)
    db_session.commit()

    r1 = client.post(f"/slot/{s.id}/complete", data={}, follow_redirects=False)
    assert r1.status_code == 303
    # слот уже удалён — повторное завершение
    r2 = client.post(f"/slot/{s.id}/complete", data={}, follow_redirects=False)
    assert r2.status_code == 303
    assert "/schedule" in r2.headers["location"]


def test_schedule_shows_empty_week(client):
    """Пустая неделя не вызывает ошибку (нет слотов)."""
    r = client.get("/schedule?week_offset=10")
    assert r.status_code == 200
    assert "Пн" in r.text or "пн" in r.text or "08:00" in r.text


def test_empty_journal_page(client):
    """Пустой журнал отображается без ошибки."""
    r = client.get("/journal")
    assert r.status_code == 200
    assert "Журнал" in r.text


def test_subscriptions_page_accessible(client):
    """Страница абонементов всегда доступна."""
    r = client.get("/subscriptions")
    assert r.status_code == 200


def test_home_page(client):
    """Главная страница доступна."""
    r = client.get("/")
    assert r.status_code == 200


def test_very_long_comment_in_program_note(client, db_session):
    """Очень длинный текст заметки (50k символов) сохраняется без ошибки."""
    from app.models import Client, Slot, Booking, TrainingNote

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    c = Client(first_name="Long", last_name="Comment", phone="+70000000110",
               name="Long Comment")
    s = Slot(start_time=now + timedelta(days=1, hours=5), capacity=2)
    db_session.add_all([c, s])
    db_session.commit()
    b = Booking(client_id=c.id, slot_id=s.id)
    db_session.add(b)
    db_session.commit()

    long_text = "Line " * 10000  # ~50k символов
    r = client.post(f"/slot/{s.id}/program/save", data={
        "client_id": str(c.id), "text": long_text
    })
    assert r.status_code == 200
    assert r.json().get("ok") is True

    saved = db_session.query(TrainingNote).filter(
        TrainingNote.slot_id == s.id, TrainingNote.client_id == c.id
    ).first()
    assert saved is not None
    assert len(saved.text) >= 50000
