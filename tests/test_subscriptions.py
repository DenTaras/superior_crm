from datetime import datetime, timedelta


def test_subscriptions_page_shows_packages(client):
    """Страница /subscriptions содержит матрицу цен."""
    r = client.get("/subscriptions")
    assert r.status_code == 200
    body = r.text
    # Заголовки
    assert "VIP" in body
    assert "Double" in body
    assert "Group" in body
    # Временные слоты
    assert "УТРО" in body
    assert "ДЕНЬ" in body
    assert "ВЕЧЕР" in body
    # Размеры пакетов
    assert "15 000" in body
    assert "28 000" in body
    assert "39 000" in body
    # Цены за занятие
    assert "занятие" in body or "за пакет" in body
    # Блок выгоды
    assert "Почему это выгодно" in body or "SUPERIOR:" in body
    # Цены за занятие
    assert "занятие" in body
    assert "пакет" in body


def test_add_subscription_increases_counter(client, db_session):
    from app.models import Client, SubscriptionPurchase

    c = Client(first_name="Sub", last_name="User", phone="+70000000010", name="Sub User")
    db_session.add(c)
    db_session.commit()

    r = client.post("/clients/add_subscription", data={
        "client_id": c.id, "time_slot": "УТРО", "format_name": "VIP", "package_size": "12",
    }, follow_redirects=False)
    assert r.status_code == 303
    # Проверяем, что покупка сохранилась с remaining
    purchase = db_session.query(SubscriptionPurchase).filter_by(client_id=c.id).first()
    assert purchase is not None
    assert purchase.remaining == 12
    assert purchase.price == 39000  # VIP УТРО 12


def test_add_subscription_different_combinations(client, db_session):
    """Разные комбинации абонементов работают."""
    from app.models import Client, SubscriptionPurchase

    c = Client(first_name="Sub2", last_name="User", phone="+70000000111", name="Sub2 User")
    db_session.add(c)
    db_session.commit()

    # Double ДЕНЬ 8
    r = client.post("/clients/add_subscription", data={
        "client_id": c.id, "time_slot": "ДЕНЬ", "format_name": "Double", "package_size": "8",
    }, follow_redirects=False)
    assert r.status_code == 303

    # Group ВЕЧЕР 4
    r = client.post("/clients/add_subscription", data={
        "client_id": c.id, "time_slot": "ВЕЧЕР", "format_name": "Group", "package_size": "4",
    }, follow_redirects=False)
    assert r.status_code == 303

    # Обе покупки имеют correct remaining
    purchases = db_session.query(SubscriptionPurchase).filter_by(client_id=c.id).order_by(SubscriptionPurchase.id).all()
    assert len(purchases) == 2
    assert purchases[0].remaining == 8
    assert purchases[1].remaining == 4


def test_subscription_deduct_from_oldest(client, db_session):
    """При завершении слота списывается из самого старого пакета."""
    from app.models import Client, Slot, Booking, SubscriptionPurchase
    from datetime import datetime, timedelta

    c = Client(first_name="SubDeduct", last_name="Test", phone="+70000000222")
    db_session.add(c)
    db_session.commit()

    # Покупаем Group УТРО 4 (старый), потом VIP ВЕЧЕР 12 (новый)
    client.post("/clients/add_subscription", data={
        "client_id": c.id, "time_slot": "УТРО", "format_name": "Group", "package_size": "4",
    }, follow_redirects=False)
    client.post("/clients/add_subscription", data={
        "client_id": c.id, "time_slot": "ВЕЧЕР", "format_name": "VIP", "package_size": "12",
    }, follow_redirects=False)

    # Создаём слот и бронь (УТРО, capacity=4 → Group — совпадает с первой покупкой)
    s = Slot(start_time=datetime.now().replace(hour=9, minute=0) + timedelta(hours=1), capacity=4)
    db_session.add(s)
    db_session.commit()
    bk = Booking(client_id=c.id, slot_id=s.id)
    db_session.add(bk)
    db_session.commit()

    # Завершаем тренировку
    r = client.post(f"/slot/{s.id}/complete", follow_redirects=False)
    assert r.status_code == 303

    # Проверяем: списалось из старшего пакета (Group УТРО 4 → осталось 3)
    purchases = db_session.query(SubscriptionPurchase).filter_by(client_id=c.id).order_by(SubscriptionPurchase.id).all()
    assert purchases[0].remaining == 3  # Group УТРО: 4-1
    assert purchases[1].remaining == 12  # VIP ВЕЧЕР: не тронут


def test_booking_respects_remaining_sessions(client, db_session):
    from app.models import Client, Slot, Booking, SubscriptionPurchase
    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    c = Client(first_name="Limit", last_name="One", phone="+70000000012", name="Limit One")
    s1 = Slot(start_time=now + timedelta(days=1, hours=0), capacity=4)
    s2 = Slot(start_time=now + timedelta(days=1, hours=1), capacity=4)
    db_session.add_all([c, s1, s2])
    db_session.commit()
    p = SubscriptionPurchase(client_id=c.id, time_slot="УТРО", format_name="Group", package_size=1, price=500, remaining=1)
    db_session.add(p)
    db_session.commit()

    # first booking should succeed
    r1 = client.post(f"/slot/{s1.id}/add", data={"client_id": c.id}, follow_redirects=False)
    assert r1.status_code == 303
    b = db_session.query(Booking).filter(Booking.client_id == c.id, Booking.slot_id == s1.id).first()
    assert b is not None

    # second booking should be blocked because remaining_sessions == 1
    r2 = client.post(f"/slot/{s2.id}/add", data={"client_id": c.id}, follow_redirects=False)
    assert r2.status_code == 303
    assert "flash=limit_reached" in r2.headers["location"]
