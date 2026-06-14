from datetime import datetime, timedelta


def test_subscriptions_page_shows_packages(client):
    """Страница /subscriptions содержит список пакетов и цены."""
    r = client.get("/subscriptions")
    assert r.status_code == 200
    body = r.text
    assert "12 занятий" in body
    assert "8 занятий" in body
    assert "4 занятия" in body


def test_add_subscription_increases_counter(client, db_session):
    from app import Client

    c = Client(first_name="Sub", last_name="User", phone="+70000000010", name="Sub User", remaining_sessions=0)
    db_session.add(c)
    db_session.commit()

    r = client.post("/clients/add_subscription", data={"client_id": c.id, "package": "12"}, follow_redirects=False)
    assert r.status_code == 303
    updated = db_session.get(Client, c.id)
    assert updated.remaining_sessions == 12


def test_booking_respects_remaining_sessions(client, db_session):
    from app import Client, Slot, Booking

    now = datetime.now().replace(second=0, microsecond=0)
    c = Client(first_name="Limit", last_name="One", phone="+70000000012", name="Limit One", remaining_sessions=1)
    s1 = Slot(start_time=now + timedelta(hours=4), capacity=2)
    s2 = Slot(start_time=now + timedelta(hours=5), capacity=2)
    db_session.add_all([c, s1, s2])
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
