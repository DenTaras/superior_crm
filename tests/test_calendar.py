from datetime import datetime, timedelta


def compute_week_start(base: datetime, week_offset: int = 0) -> datetime:
    base_week_start = (base - timedelta(days=base.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return base_week_start + timedelta(days=7 * week_offset)


def test_schedule_shows_requested_week_days(client):
    # request schedule for offset +1 week and assert day headers contain those dates
    offset = 1
    now = datetime.now()
    week_start = compute_week_start(now, offset)
    days = [week_start + timedelta(days=i) for i in range(7)]

    r = client.get(f"/schedule?week_offset={offset}")
    assert r.status_code == 200
    body = r.text
    for d in days:
        assert d.strftime("%d.%m") in body


def test_add_slot_redirects_back_to_given_week(client):
    offset = 2
    start = (datetime.now() + timedelta(days=14)).replace(second=0, microsecond=0)
    payload = {"start_time": start.strftime("%Y-%m-%dT%H:%M"), "capacity": 2, "week_offset": str(offset)}
    r = client.post("/slots/add", data=payload, follow_redirects=False)
    assert r.status_code == 303
    assert f"week_offset={offset}" in r.headers["location"]


def test_slot_link_in_schedule_includes_week_offset(client, db_session):
    # create a slot that belongs to week_offset = -1 (previous week)
    offset = -1
    from app import Slot

    week_start = compute_week_start(datetime.now(), offset)
    # pick first hour in schedule range
    slot_time = week_start + timedelta(hours=9)
    s = Slot(start_time=slot_time, capacity=2)
    db_session.add(s)
    db_session.commit()

    r = client.get(f"/schedule?week_offset={offset}")
    assert r.status_code == 200
    assert f"/slot/{s.id}?week_offset={offset}" in r.text
