from datetime import datetime, timedelta


def test_complete_slot_creates_journal_and_decrements(client, db_session):
    from app.models import Client, Slot, Booking, JournalEntry, SubscriptionPurchase

    now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    c1 = Client(first_name="J1", last_name="One", phone="+70000000020", name="J1")
    c2 = Client(first_name="J2", last_name="Two", phone="+70000000021", name="J2")
    s = Slot(start_time=now + timedelta(days=1, hours=0), capacity=4)
    db_session.add_all([c1, c2, s])
    db_session.commit()

    # Create subscription purchases for tracking
    p1 = SubscriptionPurchase(client_id=c1.id, time_slot="УТРО", format_name="Group", package_size=2, price=1000, remaining=2)
    p2 = SubscriptionPurchase(client_id=c2.id, time_slot="УТРО", format_name="Group", package_size=1, price=500, remaining=1)
    db_session.add_all([p1, p2])
    db_session.commit()

    # create bookings
    b1 = Booking(client_id=c1.id, slot_id=s.id)
    b2 = Booking(client_id=c2.id, slot_id=s.id)
    db_session.add_all([b1, b2])
    db_session.commit()

    # complete the slot
    r = client.post(f"/slot/{s.id}/complete", data={}, follow_redirects=False)
    assert r.status_code == 303

    # slot should be marked as completed (not deleted)
    from app.models import Slot as SlotModel
    completed_slot = db_session.query(SlotModel).filter(SlotModel.id == s.id).first()
    assert completed_slot is not None
    assert completed_slot.completed is True

    # bookings should remain (just marked completed)
    from app.models import Booking as BookingModel
    remaining_bookings = db_session.query(BookingModel).filter(BookingModel.slot_id == s.id).count()
    assert remaining_bookings == 2

    # SubscriptionPurchase remaining decremented (FIFO)
    upd1 = db_session.get(SubscriptionPurchase, p1.id)
    upd2 = db_session.get(SubscriptionPurchase, p2.id)
    assert upd1.remaining == 1  # c1: 2→1
    assert upd2.remaining == 0  # c2: 1→0

    # journal entry created
    entries = db_session.query(JournalEntry).all()
    assert len(entries) >= 1
    assert "J1" in entries[-1].clients or "J2" in entries[-1].clients


def test_journal_page_shows_entries(client, db_session):
    r = client.get('/journal')
    assert r.status_code == 200
    assert 'Журнал' in r.text
