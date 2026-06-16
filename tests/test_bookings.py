from datetime import datetime, timedelta


def test_add_and_remove_booking(client, db_session):
    """Тест добавления и удаления бронирования через HTTP-интерфейс.

    Создаёт клиента и слот напрямую в БД, затем добавляет бронь и удаляет её.
    """
    from app.models import Client, Slot, Booking

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
    from app.models import Client, Slot, Booking

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


def test_prevent_duplicate_booking(client, db_session):
    """Повторная попытка записать того же клиента в тот же слот не должна создавать дубликат."""
    from app.models import Client, Slot, Booking

    now = datetime.now().replace(second=0, microsecond=0)
    s = Slot(start_time=now + timedelta(hours=8), capacity=2)
    c = Client(first_name="D", last_name="Up", phone="+70000000003", name="Dup")
    db_session.add_all([s, c])
    db_session.commit()

    r1 = client.post(f"/slot/{s.id}/add", data={"client_id": c.id}, follow_redirects=False)
    assert r1.status_code == 303
    r2 = client.post(f"/slot/{s.id}/add", data={"client_id": c.id}, follow_redirects=False)
    assert r2.status_code == 303

    bookings = db_session.query(Booking).filter(Booking.slot_id == s.id, Booking.client_id == c.id).all()
    assert len(bookings) == 1


def test_db_level_unique_constraint_on_booking(client, db_session):
    """Прямая вставка дубликата в БД должна вызывать IntegrityError."""
    from app.models import Client, Slot, Booking
    from sqlalchemy.exc import IntegrityError

    now = datetime.now().replace(second=0, microsecond=0)
    s = Slot(start_time=now + timedelta(hours=9), capacity=4)
    c = Client(first_name="DB", last_name="Constraint", phone="+70000000006", name="DB Constraint")
    db_session.add_all([s, c])
    db_session.commit()

    b1 = Booking(client_id=c.id, slot_id=s.id)
    db_session.add(b1)
    db_session.commit()

    b2 = Booking(client_id=c.id, slot_id=s.id)
    db_session.add(b2)
    import pytest
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    count = db_session.query(Booking).filter(Booking.slot_id == s.id, Booking.client_id == c.id).count()
    assert count == 1


def test_training_notes_removed_on_slot_delete_and_bulk_remove(client, db_session):
    """Проверяем, что training_notes удаляются при удалении одного слота и при массовом удалении."""
    import warnings
    warnings.filterwarnings("ignore", message="Identity map already had an identity")
    from app.models import Client, Slot, TrainingNote

    now = datetime.now().replace(second=0, microsecond=0)

    # single slot delete
    s1 = Slot(start_time=now + timedelta(hours=10), capacity=2)
    c1 = Client(first_name="N1", last_name="Note", phone="+70000000004", name="Note1")
    db_session.add_all([s1, c1])
    db_session.commit()
    tn1 = TrainingNote(slot_id=s1.id, client_id=c1.id, text="note1")
    db_session.add(tn1)
    db_session.commit()

    s1_id = s1.id
    r = client.post(f"/slots/delete/{s1_id}", data={}, follow_redirects=False)
    assert r.status_code == 303
    after1 = db_session.query(TrainingNote).filter(TrainingNote.slot_id == s1_id).all()
    assert len(after1) == 0
    # bulk remove
    start = (now + timedelta(hours=20)).replace(second=0, microsecond=0)
    s2 = Slot(start_time=start + timedelta(hours=0), capacity=2)
    s3 = Slot(start_time=start + timedelta(hours=1), capacity=2)
    c2 = Client(first_name="N2", last_name="Note", phone="+70000000005", name="Note2")
    db_session.add_all([s2, s3, c2])
    db_session.commit()
    s2_id = s2.id
    s3_id = s3.id
    tn2 = TrainingNote(slot_id=s2_id, client_id=c2.id, text="note2")
    tn3 = TrainingNote(slot_id=s3_id, client_id=c2.id, text="note3")
    db_session.add_all([tn2, tn3])
    db_session.commit()

    payload = {
        "start_time": start.strftime("%Y-%m-%dT%H:%M"),
        "end_time": (start + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
    }
    r2 = client.post("/slots/remove", data=payload, follow_redirects=False)
    assert r2.status_code == 303
    after_bulk = db_session.query(TrainingNote).filter(TrainingNote.slot_id.in_([s2_id, s3_id])).all()
    assert len(after_bulk) == 0
