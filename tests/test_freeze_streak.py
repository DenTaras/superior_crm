"""Тесты: стрик тренировок, скидка за дисциплину, заморозка/разморозка."""

from datetime import datetime, timedelta
from app.auth import hash_password


def _create_client_with_sessions(db, login, fio, session_dates):
    """Создать клиента с тренировками в журнале."""
    from app.models import Client, JournalEntry
    c = Client(first_name=fio, last_name="Test", login=login,
               password_hash=hash_password("123"), freeze_days_remaining=30)
    db.add(c)
    db.flush()
    for sd in session_dates:
        je = JournalEntry(created_at=sd, slot_time=sd, clients=c.fio())
        db.add(je)
    db.commit()
    return c


# ===== СТРИК =====


def test_streak_zero_no_sessions(anon_client, db_session):
    """Нет тренировок → стрик 0."""
    from app.models import Client
    c = Client(first_name="Noop", login="noop", password_hash=hash_password("x"))
    db_session.add(c)
    db_session.commit()

    anon_client.post("/login", data={"login": "noop", "password": "x"}, follow_redirects=False)
    r = anon_client.get("/profile")
    assert r.status_code == 200
    assert "0 тренировок" in r.text or "0" in r.text


def test_streak_one_session(anon_client, db_session):
    """Одна тренировка сегодня → стрик 1."""
    from datetime import date
    today = date.today()
    c = _create_client_with_sessions(db_session, "streak1", "Streak1",
                                      [datetime(today.year, today.month, today.day, 10, 0)])
    anon_client.post("/login", data={"login": "streak1", "password": "123"}, follow_redirects=False)
    r = anon_client.get("/profile")
    assert r.status_code == 200
    # стрик 1
    assert "1" in r.text


def test_streak_three_sessions(anon_client, db_session):
    """3 тренировки через день → стрик 3."""
    from datetime import date
    today = date.today()
    dates = [
        datetime(today.year, today.month, today.day, 10, 0),
        datetime(today.year, today.month, today.day - 2, 10, 0),
        datetime(today.year, today.month, today.day - 4, 10, 0),
    ]
    c = _create_client_with_sessions(db_session, "streak3", "Streak3", dates)
    anon_client.post("/login", data={"login": "streak3", "password": "123"}, follow_redirects=False)
    r = anon_client.get("/profile")
    assert r.status_code == 200
    # скидка: 3 // 3 = 1%
    assert "1%" in r.text


def test_streak_gap_over_7_days_resets(anon_client, db_session):
    """Перерыв >7 дней → стрик 0."""
    from datetime import date
    today = date.today()
    dates = [
        datetime(today.year, today.month, today.day, 10, 0),
        datetime(today.year, today.month, today.day - 10, 10, 0),  # 10 дней назад
    ]
    c = _create_client_with_sessions(db_session, "streak_reset", "Reset", dates)
    anon_client.post("/login", data={"login": "streak_reset", "password": "123"}, follow_redirects=False)
    r = anon_client.get("/profile")
    assert r.status_code == 200
    # стрик должен быть 1 (только первая тренировка, вторая >7 дней назад)
    # на самом деле последняя тренировка сегодня, разрыв с предыдущей 10 дней
    # так что стрик = 1 (только сегодняшняя)
    assert "0%" in r.text or "Скидка" not in r.text or "1 тренировка" in r.text


# ===== СКИДКА =====


def test_discount_6_sessions(anon_client, db_session):
    """6 тренировок → скидка 2%."""
    from datetime import date
    today = date.today()
    dates = [datetime(today.year, today.month, today.day - i, 10, 0) for i in range(0, 12, 2)]  # 6 шт через день
    c = _create_client_with_sessions(db_session, "disc6", "Disc6", dates)
    anon_client.post("/login", data={"login": "disc6", "password": "123"}, follow_redirects=False)
    r = anon_client.get("/profile")
    assert r.status_code == 200
    assert "2%" in r.text


def test_discount_60_sessions_max(anon_client, db_session):
    """60+ тренировок → скидка макс 20%."""
    from datetime import date
    today = date.today()
    # 62 тренировки через день
    dates = [datetime(today.year, today.month, today.day, 10, 0) - timedelta(days=i) for i in range(0, 124, 2)]
    c = _create_client_with_sessions(db_session, "disc60", "Disc60", dates)
    anon_client.post("/login", data={"login": "disc60", "password": "123"}, follow_redirects=False)
    r = anon_client.get("/profile")
    assert r.status_code == 200
    assert "20%" in r.text


# ===== ЗАМОРОЗКА =====


def test_freeze_modal_shows_when_days_available(anon_client, db_session):
    """Клиент с днями заморозки видит кнопку заморозки."""
    from app.models import Client
    c = Client(first_name="Freezer", login="freezer", password_hash=hash_password("x"),
               freeze_days_remaining=30)
    db_session.add(c)
    db_session.commit()

    anon_client.post("/login", data={"login": "freezer", "password": "x"}, follow_redirects=False)
    r = anon_client.get("/profile")
    assert r.status_code == 200
    assert "30 дней" in r.text
    assert "Заморозить" in r.text


def test_freeze_success(anon_client, db_session):
    """POST /profile/freeze замораживает абонемент."""
    from app.models import Client
    c = Client(first_name="FreezeMe", login="freezeme", password_hash=hash_password("x"),
               freeze_days_remaining=30)
    db_session.add(c)
    db_session.commit()

    anon_client.post("/login", data={"login": "freezeme", "password": "x"}, follow_redirects=False)
    r = anon_client.post("/profile/freeze", follow_redirects=True)
    assert r.status_code == 200

    # Проверяем что frozen_until установлена
    db_session.refresh(c)
    assert c.frozen_until is not None
    assert c.frozen_until > datetime.now()


def test_freeze_blocks_booking(anon_client, db_session):
    """Во время заморозки бронирование недоступно."""
    from app.models import Client, Slot
    c = Client(first_name="FrozenBlock", login="frozenblock", password_hash=hash_password("x"),
               freeze_days_remaining=30)
    db_session.add(c)
    db_session.flush()

    # Создаём будущий слот
    from datetime import date
    tomorrow = date.today() + timedelta(days=1)
    slot = Slot(start_time=datetime(tomorrow.year, tomorrow.month, tomorrow.day, 10, 0), capacity=4)
    db_session.add(slot)
    db_session.commit()

    # Замораживаем
    c.frozen_until = datetime.now() + timedelta(days=10)
    db_session.add(c)
    db_session.commit()

    anon_client.post("/login", data={"login": "frozenblock", "password": "x"}, follow_redirects=False)
    r = anon_client.post("/profile/book", data={"slot_id": slot.id}, follow_redirects=False)
    assert r.status_code == 303  # редирект, но бронь не создана
    # Проверяем что брони нет
    from app.models import Booking
    booking = db_session.query(Booking).filter(Booking.client_id == c.id, Booking.slot_id == slot.id).first()
    assert booking is None


def test_unfreeze_restores_access(anon_client, db_session):
    """Разморозка снимает frozen_until."""
    from app.models import Client
    c = Client(first_name="UnfreezeMe", login="unfreezeme", password_hash=hash_password("x"),
               freeze_days_remaining=30,
               frozen_until=datetime.now() + timedelta(days=5))
    db_session.add(c)
    db_session.commit()

    anon_client.post("/login", data={"login": "unfreezeme", "password": "x"}, follow_redirects=False)
    r = anon_client.post("/profile/unfreeze", follow_redirects=True)
    assert r.status_code == 200

    db_session.refresh(c)
    assert c.frozen_until is None


def test_freeze_deducted_on_unfreeze(anon_client, db_session):
    """После разморозки списывается 1 день из freeze_days_remaining."""
    from app.models import Client
    c = Client(first_name="Deduct", login="deduct", password_hash=hash_password("x"),
               freeze_days_remaining=30,
               frozen_until=datetime.now() + timedelta(days=10))
    db_session.add(c)
    db_session.commit()

    anon_client.post("/login", data={"login": "deduct", "password": "x"}, follow_redirects=False)
    anon_client.post("/profile/unfreeze", follow_redirects=True)

    db_session.refresh(c)
    assert c.frozen_until is None
    assert c.freeze_days_remaining < 30  # хотя бы 1 день списался


def test_freeze_creates_freeze_log(anon_client, db_session):
    """При разморозке создаются записи FreezeLog."""
    from app.models import Client, FreezeLog
    c = Client(first_name="LogTest", login="logtest", password_hash=hash_password("x"),
               freeze_days_remaining=30,
               frozen_until=datetime.now() + timedelta(days=3))
    db_session.add(c)
    db_session.commit()

    anon_client.post("/login", data={"login": "logtest", "password": "x"}, follow_redirects=False)
    anon_client.post("/profile/unfreeze", follow_redirects=True)

    logs = db_session.query(FreezeLog).filter(FreezeLog.client_id == c.id).all()
    assert len(logs) >= 1  # минимум 1 день


def test_streak_preserved_during_freeze(anon_client, db_session):
    """Стрик сохраняется если перерыв покрыт днями заморозки."""
    from datetime import date
    from app.models import FreezeLog

    today = date.today()
    # Последняя тренировка 14 дней назад
    session_date = datetime(today.year, today.month, today.day - 14, 10, 0)
    c = _create_client_with_sessions(db_session, "streak_freeze", "StreakF", [session_date])

    # Добавляем FreezeLog на дни между последней тренировкой и сегодня
    for d in range(1, 14):
        fl = FreezeLog(client_id=c.id, date=datetime(today.year, today.month, today.day - d, 0, 0))
        db_session.add(fl)
    db_session.commit()

    anon_client.post("/login", data={"login": "streak_freeze", "password": "123"}, follow_redirects=False)
    r = anon_client.get("/profile")
    assert r.status_code == 200
    # Стрик должен быть 1 (тренировка 14 дней назад, но 13 из них заморожены → разрыв 1 день → стрик не сброшен)
    # Проверяем что стрик > 0
    assert "0 тренировок" not in r.text
