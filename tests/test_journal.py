from datetime import datetime, timedelta


def test_complete_slot_creates_journal_and_decrements(client, db_session):
    from app import Client, Slot, Booking, JournalEntry

    now = datetime.now().replace(second=0, microsecond=0)
    c1 = Client(first_name="J1", last_name="One", phone="+70000000020", name="J1", remaining_sessions=2)
    c2 = Client(first_name="J2", last_name="Two", phone="+70000000021", name="J2", remaining_sessions=1)
    s = Slot(start_time=now + timedelta(hours=4), capacity=4)
    db_session.add_all([c1, c2, s])
    db_session.commit()

    # create bookings
    b1 = Booking(client_id=c1.id, slot_id=s.id)
    b2 = Booking(client_id=c2.id, slot_id=s.id)
    db_session.add_all([b1, b2])
    db_session.commit()

    # complete the slot
    r = client.post(f"/slot/{s.id}/complete", data={}, follow_redirects=False)
    assert r.status_code == 303

    # slot should be removed
    from app import Slot as SlotModel
    assert db_session.query(SlotModel).filter(SlotModel.id == s.id).first() is None

    # bookings should be removed
    from app import Booking as BookingModel
    assert db_session.query(BookingModel).filter(BookingModel.slot_id == s.id).count() == 0

    # clients remaining_sessions decremented
    updated1 = db_session.get(Client, c1.id)
    updated2 = db_session.get(Client, c2.id)
    assert updated1.remaining_sessions == 1
    assert updated2.remaining_sessions == 0

    # journal entry created
    entries = db_session.query(JournalEntry).all()
    assert len(entries) >= 1
    assert "J1" in entries[-1].clients or "J2" in entries[-1].clients


def test_journal_page_shows_entries(client, db_session):
    r = client.get('/journal')
    assert r.status_code == 200
    assert 'Журнал' in r.text
