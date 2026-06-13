from datetime import datetime, timedelta


def test_add_and_remove_booking(client, db_session):
    """Тест добавления и удаления бронирования через HTTP-интерфейс.

    Создаёт клиента и слот напрямую в БД, затем добавляет бронь и удаляет её.
    """
    from app import Client, Slot, Booking

    # create client and slot directly in DB
    now = datetime.now().replace(second=0, microsecond=0)
    c = Client(first_name="B", last_name="User", phone="+70000000000", name="User B")
    s = Slot(start_time=now + timedelta(hours=4), capacity=2)
    db_session.add_all([c, s])
    db_session.commit()

    # add booking via POST
    r = client.post(f"/slot/{s.id}/add", data={"client_id": c.id}, follow_redirects=False)
    assert r.status_code == 303

    b = db_session.query(Booking).filter(Booking.client_id == c.id, Booking.slot_id == s.id).first()
    assert b is not None

    # remove booking
    r2 = client.post(f"/slot/{s.id}/remove", data={"client_id": c.id}, follow_redirects=False)
    assert r2.status_code == 303
    b2 = db_session.query(Booking).filter(Booking.client_id == c.id, Booking.slot_id == s.id).first()
    assert b2 is None


def test_capacity_enforced(client, db_session):
    """Тест, проверяющий что вместимость слота (`capacity`) соблюдается при добавлении броней."""
    from app import Client, Slot, Booking

    now = datetime.now().replace(second=0, microsecond=0)
    s = Slot(start_time=now + timedelta(hours=6), capacity=1)
    c1 = Client(first_name="A1", last_name="", phone="+70000000001", name="A1")
    c2 = Client(first_name="A2", last_name="", phone="+70000000002", name="A2")
    db_session.add_all([s, c1, c2])
    db_session.commit()

    # add first booking
    r1 = client.post(f"/slot/{s.id}/add", data={"client_id": c1.id}, follow_redirects=False)
    assert r1.status_code == 303
    # second should not be added because capacity == 1
    r2 = client.post(f"/slot/{s.id}/add", data={"client_id": c2.id}, follow_redirects=False)
    assert r2.status_code == 303

    bookings = db_session.query(Booking).filter(Booking.slot_id == s.id).all()
    assert len(bookings) == 1
