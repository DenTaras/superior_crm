"""Тесты привязки абонементов к временным слотам.

Проверяет:
- Покупка по 1 занятию каждой из 9 комбинаций (3 time_slot × 3 format)
- Запись в слот возможна только при наличии пакета для этого time_slot
- При завершении тренировки списывается из пакета, соответствующего time_slot
"""

from datetime import datetime, timedelta


def test_buy_all_combos_and_book_matching_slots(client, db_session):
    """Клиент покупает по 1 занятию каждой комбинации и записывается в УТРО/ДЕНЬ/ВЕЧЕР."""
    from app.models import Client, Slot, Booking, SubscriptionPurchase
    from app.pricing import get_price, slot_time_slot, format_from_capacity

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    c = Client(first_name="TimeSlot", last_name="Test", phone="+79990000001")
    db_session.add(c)
    db_session.commit()

    # 1. Покупаем по 1 занятию каждой комбинации (9 штук)
    combos = [
        ("УТРО", "VIP"), ("УТРО", "Double"), ("УТРО", "Group"),
        ("ДЕНЬ", "VIP"), ("ДЕНЬ", "Double"), ("ДЕНЬ", "Group"),
        ("ВЕЧЕР", "VIP"), ("ВЕЧЕР", "Double"), ("ВЕЧЕР", "Group"),
    ]
    fmt_to_cap = {"VIP": 1, "Double": 2, "Group": 4}
    for ts, fmt in combos:
        price = get_price(ts, fmt, 1)
        p = SubscriptionPurchase(
            client_id=c.id, time_slot=ts, format_name=fmt,
            package_size=1, price=price, remaining=1,
        )
        db_session.add(p)
    db_session.commit()

    # 2. Создаём по слоту для каждой комбинации (формат → capacity)
    slots = []
    for i, (ts, fmt) in enumerate(combos):
        cap = fmt_to_cap[fmt]
        hour_offsets = {"УТРО": 0, "ДЕНЬ": 4, "ВЕЧЕР": 9}
        s = Slot(
            start_time=now + timedelta(days=1, hours=hour_offsets[ts]) + timedelta(hours=i * 0.1),
            capacity=cap,
        )
        slots.append(s)
    db_session.add_all(slots)
    db_session.commit()

    for s in slots:
        assert format_from_capacity(s.capacity) in ("VIP", "Double", "Group")

    # 3. Записываемся в каждый слот — формат и time_slot должны совпадать
    booked_count = 0
    for s in slots:
        r = client.post(f"/slot/{s.id}/add", data={"client_id": c.id}, follow_redirects=False)
        if r.status_code == 303 and "flash" not in r.headers.get("location", ""):
            booked_count += 1
    assert booked_count == 9, f"Ожидалось 9 успешных броней, получено {booked_count}"

    bookings = db_session.query(Booking).filter(Booking.client_id == c.id).all()
    assert len(bookings) == 9


def test_booking_blocked_without_matching_time_slot(client, db_session):
    """Запись в слот отклоняется, если нет пакета для этого time_slot."""
    from app.models import Client, Slot, Booking, SubscriptionPurchase
    from app.pricing import slot_time_slot

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    c = Client(first_name="NoMatch", last_name="Slot", phone="+79990000002")
    db_session.add(c)
    db_session.commit()

    # Покупаем только УТРО
    p = SubscriptionPurchase(
        client_id=c.id, time_slot="УТРО", format_name="Group",
        package_size=1, price=3200, remaining=1,
    )
    db_session.add(p)
    db_session.commit()

    # Пробуем записаться в ДЕНЬ
    day_slot = Slot(start_time=now + timedelta(days=1, hours=4), capacity=2)   # 13:00 → ДЕНЬ
    db_session.add(day_slot)
    db_session.commit()
    assert slot_time_slot(day_slot.start_time) == "ДЕНЬ"

    r = client.post(f"/slot/{day_slot.id}/add", data={"client_id": c.id}, follow_redirects=False)
    assert r.status_code == 303
    assert "flash=limit_reached" in r.headers["location"], (
        "Должно быть отказано: нет ДЕНЬ пакета"
    )

    # Пробуем записаться в ВЕЧЕР
    evening_slot = Slot(start_time=now + timedelta(days=1, hours=9), capacity=4)  # 18:00 → ВЕЧЕР
    db_session.add(evening_slot)
    db_session.commit()

    r = client.post(f"/slot/{evening_slot.id}/add", data={"client_id": c.id}, follow_redirects=False)
    assert r.status_code == 303
    assert "flash=limit_reached" in r.headers["location"], (
        "Должно быть отказано: нет ВЕЧЕР пакета"
    )

    # Запись в УТРО должна пройти
    morning_slot = Slot(start_time=now + timedelta(days=1, hours=0), capacity=4)  # 9:00 → УТРО (Group)
    db_session.add(morning_slot)
    db_session.commit()
    assert slot_time_slot(morning_slot.start_time) == "УТРО"

    r = client.post(f"/slot/{morning_slot.id}/add", data={"client_id": c.id}, follow_redirects=False)
    assert r.status_code == 303
    assert "flash" not in r.headers["location"], "УТРО запись должна пройти"

    b = db_session.query(Booking).filter(
        Booking.client_id == c.id, Booking.slot_id == morning_slot.id
    ).first()
    assert b is not None


def test_completion_deducts_from_matching_time_slot_only(client, db_session):
    """При завершении тренировки списывается из пакета соответствующего time_slot."""
    from app.models import Client, Slot, Booking, SubscriptionPurchase
    from app.pricing import slot_time_slot

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    c = Client(first_name="Deduct", last_name="BySlot", phone="+79990000003")
    db_session.add(c)
    db_session.commit()

    # Покупаем: УТРО-VIP 1шт и ДЕНЬ-Group 1шт
    p1 = SubscriptionPurchase(
        client_id=c.id, time_slot="УТРО", format_name="VIP",
        package_size=1, price=5200, remaining=1,
    )
    p2 = SubscriptionPurchase(
        client_id=c.id, time_slot="ДЕНЬ", format_name="Group",
        package_size=1, price=2560, remaining=1,
    )
    db_session.add_all([p1, p2])
    db_session.commit()

    # Создаём слот ДЕНЬ и записываемся (POST уже создаёт Booking)
    day_slot = Slot(start_time=now + timedelta(days=1, hours=4), capacity=4)   # 13:00 → ДЕНЬ (Group)
    db_session.add(day_slot)
    db_session.commit()
    r = client.post(f"/slot/{day_slot.id}/add", data={"client_id": c.id}, follow_redirects=False)
    assert r.status_code == 303

    # Завершаем тренировку
    r = client.post(f"/slot/{day_slot.id}/complete", follow_redirects=False)
    assert r.status_code == 303

    # Проверяем: списалось только из ДЕНЬ (p2), УТРО (p1) не тронут
    u1 = db_session.get(SubscriptionPurchase, p1.id)
    u2 = db_session.get(SubscriptionPurchase, p2.id)
    assert u1.remaining == 1, "УТРО пакет не должен быть затронут"
    assert u2.remaining == 0, "ДЕНЬ пакет должен быть списан"


def test_completion_prefers_exact_time_slot_over_fallback(client, db_session):
    """Если есть несколько пакетов, списывается из точного совпадения time_slot, а не из любого."""
    from app.models import Client, Slot, Booking, SubscriptionPurchase
    from app.pricing import slot_time_slot

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    c = Client(first_name="Prefer", last_name="Exact", phone="+79990000004")
    db_session.add(c)
    db_session.commit()

    # УТРО: 1 занятие, ВЕЧЕР: 1 занятие
    p_utro = SubscriptionPurchase(
        client_id=c.id, time_slot="УТРО", format_name="Group",
        package_size=1, price=3200, remaining=1,
    )
    p_vecher = SubscriptionPurchase(
        client_id=c.id, time_slot="ВЕЧЕР", format_name="VIP",
        package_size=1, price=6760, remaining=1,
    )
    db_session.add_all([p_utro, p_vecher])
    db_session.commit()

    # Записываемся в ВЕЧЕР (POST создаёт Booking)
    evening_slot = Slot(start_time=now + timedelta(days=1, hours=10), capacity=1)  # 19:00 → ВЕЧЕР (VIP)
    db_session.add(evening_slot)
    db_session.commit()
    assert slot_time_slot(evening_slot.start_time) == "ВЕЧЕР"
    r = client.post(f"/slot/{evening_slot.id}/add", data={"client_id": c.id}, follow_redirects=False)
    assert r.status_code == 303

    # Завершаем
    r = client.post(f"/slot/{evening_slot.id}/complete", follow_redirects=False)
    assert r.status_code == 303

    # Проверяем: списался ВЕЧЕР, УТРО не тронут
    assert db_session.get(SubscriptionPurchase, p_utro.id).remaining == 1
    assert db_session.get(SubscriptionPurchase, p_vecher.id).remaining == 0


def test_clients_page_groups_identical_packages(client, db_session):
    """Страница клиентов группирует одинаковые (format_name, time_slot) пакеты."""
    from app.models import Client, SubscriptionPurchase, Booking

    # Очищаем тестовые данные от предыдущих тестов
    db_session.query(Booking).delete()
    db_session.query(SubscriptionPurchase).delete()
    db_session.query(Client).delete()
    db_session.commit()

    c = Client(first_name="Grouped", last_name="Test", phone="+79990000005")
    db_session.add(c)
    db_session.commit()

    # Две покупки Group ВЕЧЕР: 4 + 1 = 5 суммарно
    db_session.add_all([
        SubscriptionPurchase(client_id=c.id, time_slot="ВЕЧЕР", format_name="Group", package_size=4, price=12480, remaining=4),
        SubscriptionPurchase(client_id=c.id, time_slot="ВЕЧЕР", format_name="Group", package_size=1, price=4160, remaining=1),
        SubscriptionPurchase(client_id=c.id, time_slot="УТРО", format_name="VIP", package_size=3, price=15600, remaining=3),
    ])
    db_session.commit()

    # Verify data is in DB
    from sqlalchemy import func
    cnt = db_session.query(func.count(SubscriptionPurchase.id)).filter(
        SubscriptionPurchase.client_id == c.id,
    ).scalar()
    assert cnt == 3, f"Expected 3 purchases, got {cnt}"

    r = client.get("/clients")
    assert r.status_code == 200

    # Проверяем: Group ВЕЧЕР с 5 остатком (сгруппировано из 4+1)
    assert "Group ВЕЧЕР: 5/" in r.text, f"Expected grouped 'Group ВЕЧЕР: 5/' in page"
    # VIP УТРО должно быть 3
    assert "VIP УТРО: 3/" in r.text, f"Expected 'VIP УТРО: 3/' in page"


def test_clients_page_shows_booked_by_time_slot(client, db_session):
    """Страница клиентов показывает booked_future для каждого time_slot."""
    from app.models import Client, Slot, Booking, SubscriptionPurchase

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    # Очищаем тестовые данные от предыдущих тестов
    db_session.query(Booking).delete()
    db_session.query(SubscriptionPurchase).delete()
    db_session.query(Client).delete()
    db_session.commit()

    c = Client(first_name="BookedBy", last_name="Slot", phone="+79990000006")
    db_session.add(c)
    db_session.commit()

    # Одна покупка VIP ДЕНЬ
    db_session.add(SubscriptionPurchase(client_id=c.id, time_slot="ДЕНЬ", format_name="VIP", package_size=4, price=12480, remaining=4))
    db_session.commit()

    # Создаём 2 будущих брони в ДЕНЬ
    s1 = Slot(start_time=now + timedelta(days=1, hours=4), capacity=4)   # 13:00 → ДЕНЬ
    s2 = Slot(start_time=now + timedelta(days=2, hours=5), capacity=4)   # 14:00 → ДЕНЬ
    db_session.add_all([s1, s2])
    db_session.commit()
    db_session.add(Booking(client_id=c.id, slot_id=s1.id))
    db_session.add(Booking(client_id=c.id, slot_id=s2.id))
    db_session.commit()

    r = client.get("/clients")
    assert r.status_code == 200
    # Должно быть VIP ДЕНЬ: 4/2 (4 осталось, 2 забронировано)
    assert "VIP ДЕНЬ: 4/2" in r.text


def test_profile_page_shows_same_data_as_clients_page(anon_client, db_session):
    """Профиль клиента показывает те же grouped данные, что и страница клиентов."""
    from app.models import Client, Slot, Booking, SubscriptionPurchase
    from app.auth import hash_password
    from datetime import datetime, timedelta

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    c = Client(first_name="Profile", last_name="Match", phone="+79990000007",
               login="profile_match", password_hash=hash_password("secret"))
    db_session.add(c)
    db_session.flush()

    # Покупки: Group УТРО 2шт, Double ВЕЧЕР 3шт
    db_session.add_all([
        SubscriptionPurchase(client_id=c.id, time_slot="УТРО", format_name="Group", package_size=2, price=6400, remaining=2),
        SubscriptionPurchase(client_id=c.id, time_slot="ВЕЧЕР", format_name="Double", package_size=3, price=15600, remaining=3),
    ])
    # 1 бронь в УТРО
    s = Slot(start_time=now + timedelta(days=1, hours=1), capacity=4)  # 10:00 → УТРО
    db_session.add(s)
    db_session.commit()
    db_session.add(Booking(client_id=c.id, slot_id=s.id))
    db_session.commit()

    # Логинимся как этот клиент и проверяем профиль
    r = anon_client.post("/login", data={"login": "profile_match", "password": "secret"}, follow_redirects=False)
    assert r.status_code == 303, f"Login failed: {r.status_code}, location: {r.headers.get('location', 'N/A')}"

    r = anon_client.get("/profile")
    assert r.status_code == 200
    # Group УТРО: 2/1 (2 осталось, 1 забронировано)
    assert "Group УТРО: 2/1" in r.text, f"Expected 'Group УТРО: 2/1' in profile"
    # Double ВЕЧЕР: 3/0 (3 осталось, 0 забронировано)
    assert "Double ВЕЧЕР: 3/0" in r.text, f"Expected 'Double ВЕЧЕР: 3/0' in profile"
