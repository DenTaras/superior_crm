from datetime import datetime, timedelta


def iso_no_seconds(dt):
    return dt.replace(second=0, microsecond=0).isoformat()


def test_add_slot_and_conflict(client):
    # choose a time in the near future
    start = (datetime.now() + timedelta(hours=2)).replace(second=0, microsecond=0)
    payload = {"start_time": start.strftime("%Y-%m-%dT%H:%M"), "capacity": 2}
    r = client.post("/slots/add", data=payload, follow_redirects=False)
    assert r.status_code == 303
    assert "/schedule" in r.headers["location"]

    # try to add same slot again -> should redirect with flash=slot_conflict
    r2 = client.post("/slots/add", data=payload, follow_redirects=False)
    assert r2.status_code == 303
    assert "flash=slot_conflict" in r2.headers["location"]


def test_edit_slot_conflict(client, db_session):
    # create two slots directly in DB
    from app import Slot

    now = datetime.now().replace(second=0, microsecond=0)
    s1 = Slot(start_time=now + timedelta(hours=5), capacity=2)
    s2 = Slot(start_time=now + timedelta(hours=7), capacity=2)
    db_session.add_all([s1, s2])
    db_session.commit()

    # try to move s2 to time overlapping s1
    payload = {"start_time": (now + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M"), "capacity": 2}
    r = client.post(f"/slots/edit/{s2.id}", data=payload, follow_redirects=False)
    assert r.status_code == 303
    assert "flash=slot_conflict" in r.headers["location"]
