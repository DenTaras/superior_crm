"""Тесты flash-уведомлений."""

import re


def test_flash_modal_rendered_with_conflict(client):
    """Flash-модалка отображается при параметре flash=slot_conflict."""
    r = client.get("/schedule?flash=slot_conflict")
    assert r.status_code == 200
    assert "flash-modal" in r.text
    assert "Время пересекается" in r.text
    assert "flash-countdown" in r.text


def test_flash_modal_rendered_with_limit(client):
    """Flash-модалка отображается при параметре flash=limit_reached."""
    r = client.get("/schedule?flash=limit_reached")
    assert r.status_code == 200
    assert "flash-modal" in r.text
    assert "нет доступных занятий" in r.text
    assert "flash-countdown" in r.text


def test_flash_modal_rendered_with_past(client):
    """Flash-модалка отображается при параметре flash=slot_past."""
    r = client.get("/schedule?flash=slot_past")
    assert r.status_code == 200
    assert "flash-modal" in r.text
    assert "прошлое" in r.text
    assert "flash-countdown" in r.text


def test_flash_modal_not_rendered_without_flash(client):
    """Без параметра flash модалка не отображается."""
    r = client.get("/schedule")
    assert r.status_code == 200
    assert "flash-modal" not in r.text


def test_flash_modal_countdown_js_present(client):
    """JS-код автоскрытия присутствует на странице с flash."""
    r = client.get("/schedule?flash=slot_conflict")
    assert r.status_code == 200
    # Проверяем что JS содержит таймер
    assert "setInterval" in r.text
    assert "seconds--" in r.text or "seconds-&gt;" in r.text
    assert "clearInterval" in r.text
    # Проверяем что initial значение 5
    assert ">5<" in r.text or '"5"' in r.text or "5 с" in r.text


def test_flash_ok_link_contains_week_offset(client):
    """Ссылка ОК в flash сохраняет week_offset."""
    r = client.get("/schedule?flash=slot_conflict&week_offset=2")
    assert r.status_code == 200
    # Проверяем что в HTML есть href с week_offset=2
    assert "week_offset=2" in r.text


def test_flash_on_slot_page(client, db_session):
    """Flash-модалка работает и на странице слота."""
    from app.models import Slot
    from datetime import datetime, timezone, timedelta

    s = Slot(start_time=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=3), capacity=2)
    db_session.add(s)
    db_session.commit()

    r = client.get(f"/slot/{s.id}?flash=limit_reached")
    assert r.status_code == 200
    assert "flash-modal" in r.text
    assert "flash-countdown" in r.text
    assert "нет доступных занятий" in r.text
    assert "replaceState" in r.text, "URL не очищается после закрытия"


def test_flash_url_cleaned_on_close(client):
    """JS-код содержит replaceState для очистки URL после закрытия flash."""
    r = client.get("/schedule?flash=slot_conflict")
    assert r.status_code == 200
    assert "replaceState" in r.text


def test_flash_custom_seconds(client):
    """Параметр flash_seconds=1 устанавливает data-seconds=1."""
    r = client.get("/schedule?flash=slot_conflict&flash_seconds=1")
    assert r.status_code == 200
    assert 'data-seconds="1"' in r.text
    assert "data-seconds" in r.text
