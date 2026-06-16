from datetime import datetime, timedelta
import re
import json
import html

import pytest

from app.models import Client, Slot, Booking, TrainingNote, JournalEntry


def extract_notes_json(html_text: str) -> dict:
    m = re.search(r'<script id="notes-data" type="application/json">(.*?)</script>', html_text, re.S)
    if not m:
        return {}
    try:
        raw = m.group(1)
        return json.loads(raw)
    except Exception:
        return {}


def test_program_save_and_persistence(client, db_session):
    # create two clients
    c1 = Client(first_name='One', last_name='Client', name='Client One')
    c2 = Client(first_name='Two', last_name='Client', name='Client Two')
    db_session.add_all([c1, c2])
    db_session.commit()

    # create a slot in the future
    slot = Slot(start_time=datetime.now() + timedelta(days=1, hours=1), capacity=2)
    db_session.add(slot)
    db_session.commit()

    # book both clients into the slot
    b1 = Booking(client_id=c1.id, slot_id=slot.id)
    b2 = Booking(client_id=c2.id, slot_id=slot.id)
    db_session.add_all([b1, b2])
    db_session.commit()

    # page loads — notes should be empty initially
    r = client.get(f"/slot/{slot.id}/program")
    assert r.status_code == 200
    notes_initial = extract_notes_json(r.text)
    assert str(c1.id) in notes_initial
    assert notes_initial[str(c1.id)] == ''
    assert str(c2.id) in notes_initial
    assert notes_initial[str(c2.id)] == ''

    # save note for client 1 using form post
    r = client.post(f"/slot/{slot.id}/program/save", data={
        'client_id': str(c1.id), 'text': 'note for one'
    })
    assert r.status_code == 200
    assert r.json().get('ok') is True

    # ensure TrainingNote exists in DB
    tn = db_session.query(TrainingNote).filter(TrainingNote.slot_id == slot.id, TrainingNote.client_id == c1.id).first()
    assert tn is not None and tn.text == 'note for one'

    # reload program page and verify note appears in HTML
    r2 = client.get(f"/slot/{slot.id}/program")
    assert r2.status_code == 200
    notes_after_reload = extract_notes_json(r2.text)
    assert notes_after_reload.get(str(c1.id)) == 'note for one'
    assert str(c2.id) in notes_after_reload
    assert notes_after_reload[str(c2.id)] == ''

    # simulate sendBeacon/raw body save for client 2 (text/plain body)
    payload = f"client_id={c2.id}&text={"note for two"}"
    # send as raw body with content-type text/plain (endpoint will parse)
    r3 = client.post(f"/slot/{slot.id}/program/save", data=payload, headers={"Content-Type": "text/plain"})
    assert r3.status_code == 200
    assert r3.json().get('ok') is True

    tn2 = (db_session.query(TrainingNote)
           .filter(TrainingNote.slot_id == slot.id, TrainingNote.client_id == c2.id)
           .first())
    assert tn2 is not None and tn2.text == 'note for two'

    # reload program page and verify both notes appear in HTML
    r4 = client.get(f"/slot/{slot.id}/program")
    assert r4.status_code == 200
    notes_after_both = extract_notes_json(r4.text)
    assert str(c1.id) in notes_after_both
    assert str(c2.id) in notes_after_both
    assert notes_after_both[str(c1.id)] == 'note for one'
    assert notes_after_both[str(c2.id)] == 'note for two'

    # complete the slot -> should copy notes to journal and remove training notes
    r5 = client.post(f"/slot/{slot.id}/complete", data={'week_offset': 0})
    # redirect to /journal
    assert r5.status_code in (200, 307, 303, 302)

    # check journal entry has comments mapping
    je = db_session.query(JournalEntry).order_by(JournalEntry.created_at.desc()).first()
    assert je is not None
    assert je.comments
    jm = json.loads(je.comments)
    assert jm.get(str(c1.id)) == 'note for one'
    assert jm.get(str(c2.id)) == 'note for two'

    # training notes for this slot should be removed
    tn_after = db_session.query(TrainingNote).filter(TrainingNote.slot_id == slot.id).all()
    assert len(tn_after) == 0
