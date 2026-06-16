"""Тесты производительности и работы с большими объёмами данных.

Проверяет:
- Скорость ответа страниц при большом количестве слотов/клиентов/записей
- Массовое создание слотов через bulk-интервал
- Множественные сохранения заметок
- Стабильность при больших нагрузках (stress-подобные сценарии)
"""

from datetime import datetime, timedelta
import time

import pytest

# Константы для нагрузочных тестов
MANY_SLOTS = 150
MANY_CLIENTS = 100
MANY_NOTES = 50


def test_schedule_performance_with_many_slots(client, db_session):
    """Страница расписания с ~150 слотами загружается быстро (< 2 сек)."""
    from app import Slot

    now = datetime.now().replace(second=0, microsecond=0)
    week_start = (now - timedelta(days=now.weekday())).replace(hour=8, minute=0, second=0, microsecond=0)
    slots = []
    for i in range(MANY_SLOTS):
        slots.append(Slot(start_time=week_start + timedelta(hours=i), capacity=2))
    db_session.add_all(slots)
    db_session.commit()

    start = time.time()
    r = client.get("/schedule")
    elapsed = time.time() - start

    assert r.status_code == 200
    assert elapsed < 2.0, f"Страница расписания загружалась {elapsed:.2f} сек (лимит 2.0)"


def test_journal_performance_with_many_entries(client, db_session):
    """Страница журнала со 100+ записей загружается быстро (< 2 сек)."""
    from app import JournalEntry

    entries = []
    for i in range(MANY_CLIENTS):
        entries.append(JournalEntry(
            slot_time=datetime.now(),
            clients=f"Client {i}",
            comments='{"1": "note"}',
        ))
    db_session.add_all(entries)
    db_session.commit()

    start = time.time()
    r = client.get("/journal")
    elapsed = time.time() - start

    assert r.status_code == 200
    assert elapsed < 2.0, f"Страница журнала загружалась {elapsed:.2f} сек (лимит 2.0)"


def test_many_clients_page_loads(client, db_session):
    """Страница клиентов со 100 записями загружается быстро (< 2 сек)."""
    from app import Client

    clients = []
    for i in range(MANY_CLIENTS):
        clients.append(Client(
            first_name=f"First{i}", last_name=f"Last{i}",
            phone=f"+7000000{i:04d}", name=f"Client {i}",
            remaining_sessions=1,
        ))
    db_session.add_all(clients)
    db_session.commit()

    start = time.time()
    r = client.get("/clients")
    elapsed = time.time() - start

    assert r.status_code == 200
    assert elapsed < 2.0, f"Страница клиентов загружалась {elapsed:.2f} сек (лимит 2.0)"


def test_bulk_slot_creation_performance(client, db_session):
    """Массовое создание 24 слотов (сутки) через bulk-интервал работает быстро (< 3 сек)."""
    now = datetime.now().replace(second=0, microsecond=0)
    # планируем на завтра, чтобы не было конфликтов
    tomorrow = now + timedelta(days=1)
    start_dt = tomorrow.replace(hour=8, minute=0, second=0, microsecond=0)
    end_dt = tomorrow.replace(hour=22, minute=0, second=0, microsecond=0)

    payload = {
        "start_time": start_dt.strftime("%Y-%m-%dT%H:%M"),
        "end_time": end_dt.strftime("%Y-%m-%dT%H:%M"),
        "capacity": 2,
    }

    start = time.time()
    r = client.post("/slots/add", data=payload, follow_redirects=False)
    elapsed = time.time() - start

    assert r.status_code == 303
    assert elapsed < 3.0, f"Bulk-создание 14 слотов заняло {elapsed:.2f} сек (лимит 3.0)"


def test_many_program_saves_performance(client, db_session):
    """Многократное сохранение заметок (50 раз) работает стабильно."""
    from app import Client, Slot, Booking, TrainingNote

    now = datetime.now().replace(second=0, microsecond=0)
    c = Client(first_name="Stress", last_name="Save", phone="+70000000999",
               name="Stress Save")
    s = Slot(start_time=now + timedelta(days=2, hours=1), capacity=2)
    db_session.add_all([c, s])
    db_session.commit()
    b = Booking(client_id=c.id, slot_id=s.id)
    db_session.add(b)
    db_session.commit()

    start = time.time()
    for i in range(MANY_NOTES):
        r = client.post(f"/slot/{s.id}/program/save", data={
            "client_id": str(c.id), "text": f"Note version {i}"
        })
        assert r.status_code == 200
        assert r.json().get("ok") is True
    elapsed = time.time() - start

    assert elapsed < 5.0, f"{MANY_NOTES} сохранений заняли {elapsed:.2f} сек (лимит 5.0)"

    # финальная версия сохранилась
    final_note = db_session.query(TrainingNote).filter(
        TrainingNote.slot_id == s.id, TrainingNote.client_id == c.id
    ).first()
    assert final_note is not None
    assert final_note.text == f"Note version {MANY_NOTES - 1}"


def test_concurrent_like_booking_requests(client, db_session):
    """Симуляция конкурентных запросов на запись в один слот.

    Отправляет много запросов подряд — слот должен принять ровно столько,
    сколько позволяет capacity.
    """
    from app import Client, Slot, Booking

    now = datetime.now().replace(second=0, microsecond=0)
    s = Slot(start_time=now + timedelta(days=1, hours=6), capacity=4)
    db_session.add(s)
    db_session.commit()

    clients = []
    for i in range(10):
        c = Client(first_name=f"Race{i}", last_name="Client",
                   phone=f"+7000000{i:04d}", name=f"Race {i}",
                   remaining_sessions=5)
        clients.append(c)
    db_session.add_all(clients)
    db_session.commit()

    # отправляем 10 запросов на запись в слот capacity=4
    for c in clients:
        client.post(f"/slot/{s.id}/add", data={"client_id": c.id}, follow_redirects=False)

    total = db_session.query(Booking).filter(Booking.slot_id == s.id).count()
    assert total == 4, f"Ожидалось 4 брони, получено {total}"


def test_slot_page_performance_with_many_clients(client, db_session):
    """Страница слота с 20 записанными клиентами загружается быстро (< 1.5 сек)."""
    from app import Client, Slot, Booking

    now = datetime.now().replace(second=0, microsecond=0)
    s = Slot(start_time=now + timedelta(days=1, hours=7), capacity=20)
    db_session.add(s)
    db_session.commit()

    for i in range(20):
        c = Client(first_name=f"SlotPerf{i}", last_name="Client",
                   phone=f"+7000000{i:04d}", name=f"Perf {i}",
                   remaining_sessions=5)
        db_session.add(c)
        db_session.commit()
        b = Booking(client_id=c.id, slot_id=s.id)
        db_session.add(b)
        db_session.commit()

    start = time.time()
    r = client.get(f"/slot/{s.id}")
    elapsed = time.time() - start

    assert r.status_code == 200
    assert elapsed < 1.5, f"Страница слота загружалась {elapsed:.2f} сек (лимит 1.5)"


def test_program_page_performance_with_many_clients(client, db_session):
    """Страница программы с 20 клиентами + заметки загружается быстро (< 1.5 сек)."""
    from app import Client, Slot, Booking, TrainingNote

    now = datetime.now().replace(second=0, microsecond=0)
    s = Slot(start_time=now + timedelta(days=1, hours=8), capacity=20)
    db_session.add(s)
    db_session.commit()

    for i in range(20):
        c = Client(first_name=f"ProgPerf{i}", last_name="Client",
                   phone=f"+7000000{i:04d}", name=f"Prog {i}",
                   remaining_sessions=5)
        db_session.add(c)
        db_session.commit()
        b = Booking(client_id=c.id, slot_id=s.id)
        db_session.add(b)
        note = TrainingNote(slot_id=s.id, client_id=c.id, text=f"Note for client {i}")
        db_session.add(note)
        db_session.commit()

    start = time.time()
    r = client.get(f"/slot/{s.id}/program")
    elapsed = time.time() - start

    assert r.status_code == 200
    assert elapsed < 1.5, f"Страница программы загружалась {elapsed:.2f} сек (лимит 1.5)"


def test_mass_slot_deletion_performance(client, db_session):
    """Массовое удаление большого количества слотов работает быстро (< 3 сек)."""
    from app import Slot

    now = datetime.now().replace(second=0, microsecond=0)
    # создаём слоты на завтра
    tomorrow = now + timedelta(days=1)
    slots = []
    for i in range(50):
        slots.append(Slot(start_time=tomorrow.replace(hour=8 + i % 12, minute=0), capacity=2))
    db_session.add_all(slots)
    db_session.commit()

    start_dt = tomorrow.replace(hour=8, minute=0)
    end_dt = tomorrow.replace(hour=22, minute=0)

    start = time.time()
    r = client.post("/slots/remove", data={
        "start_time": start_dt.strftime("%Y-%m-%dT%H:%M"),
        "end_time": end_dt.strftime("%Y-%m-%dT%H:%M"),
    }, follow_redirects=False)
    elapsed = time.time() - start

    assert r.status_code == 303
    assert elapsed < 3.0, f"Массовое удаление заняло {elapsed:.2f} сек (лимит 3.0)"
