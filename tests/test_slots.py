from datetime import datetime, timedelta


def iso_no_seconds(dt):
    """Вспомогательная функция: возвращает ISO-строку без секунд и микросекунд."""
    return dt.replace(second=0, microsecond=0).isoformat()


def test_add_slot_and_conflict(client):
    """Тест добавления слота и обработки конфликта добавления дубликата.

    Проверяет успешный редирект при создании и флаг конфликта при повторной попытке.
    """
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
    """Тест редактирования слота, при котором новое время конфликтует с другим слотом."""
    # create two slots directly in DB
    from app.models import Slot

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


def test_cannot_create_slot_in_past(client):
    """Нельзя создать слот в прошлом."""
    start = (datetime.now() - timedelta(hours=2)).replace(second=0, microsecond=0)
    payload = {"start_time": start.strftime("%Y-%m-%dT%H:%M"), "capacity": 2}
    r = client.post("/slots/add", data=payload, follow_redirects=False)
    assert r.status_code == 303
    assert "flash=slot_past" in r.headers["location"]


def test_cannot_edit_slot_to_past(client, db_session):
    """Нельзя переместить существующий слот в прошлое."""
    from app.models import Slot

    now = datetime.now().replace(second=0, microsecond=0)
    s = Slot(start_time=now + timedelta(hours=5), capacity=2)
    db_session.add(s)
    db_session.commit()

    payload = {"start_time": (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"), "capacity": 2}
    r = client.post(f"/slots/edit/{s.id}", data=payload, follow_redirects=False)
    assert r.status_code == 303
    assert "flash=slot_past" in r.headers["location"]
