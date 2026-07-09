"""Тесты публичных страниц: заявка на тренировку, контакты.

Внимание: тесты используют db_session, который разделяется между тестами
через engine (session-scoped). Поэтому каждый тест проверяет ТОЛЬКО
свои данные, не полагаясь на состояние таблицы.
"""

import re


def test_contacts_page_available(anon_client):
    """GET /contacts — страница доступна без авторизации."""
    r = anon_client.get("/contacts")
    assert r.status_code == 200
    assert "Контакты" in r.text
    assert "Адрес" in r.text or "адрес" in r.text
    assert "+7" in r.text
    assert "Instagram" in r.text or "instagram" in r.text
    assert "Telegram" in r.text or "telegram" in r.text
    assert "Режим работы" in r.text
    assert "2ГИС" in r.text or "2gis" in r.text
    assert 'href="/"' in r.text  # ссылка на главную через base.html


def test_contacts_nav_link_exists(anon_client):
    """На главной странице есть ссылка 'Контакты' для анонима."""
    r = anon_client.get("/")
    assert r.status_code == 200
    assert '/contacts"' in r.text
    assert "Контакты" in r.text


def test_signup_page_available(anon_client):
    """GET /signup — страница доступна, содержит форму."""
    r = anon_client.get("/signup")
    assert r.status_code == 200
    assert "Имя" in r.text
    assert "Фамилия" in r.text
    assert "Телефон" in r.text
    assert "Цель тренировок" in r.text
    assert "Предпочитаемое время" in r.text
    assert "Отправить заявку" in r.text
    assert 'action="/signup"' in r.text
    assert "csrf_token" in r.text


def test_signup_with_all_fields(anon_client, db_session):
    """POST /signup со всеми полями сохраняет заявку."""
    from app.models import TrainingRequest

    r = anon_client.post("/signup", data={
        "first_name": "Иван",
        "last_name": "Петров",
        "phone": "+79991112233",
        "goal": "Похудеть и подтянуться",
        "preferred_time": "Утро будних дней",
        "pd_consent": "true",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "Ваша заявка принята" in r.text

    req = db_session.query(TrainingRequest).filter_by(first_name="Иван").first()
    assert req is not None
    assert req.last_name == "Петров"
    assert req.phone == "+79991112233"
    assert req.goal == "Похудеть и подтянуться"
    assert req.preferred_time == "Утро будних дней"


def test_signup_minimal_fields(anon_client, db_session):
    """POST /signup только с first_name."""
    from app.models import TrainingRequest

    r = anon_client.post("/signup", data={
        "first_name": "Мария",
        "pd_consent": "true",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "Ваша заявка принята" in r.text

    req = db_session.query(TrainingRequest).filter_by(first_name="Мария").first()
    assert req is not None
    assert req.last_name == ""
    assert req.phone == ""
    assert req.goal == ""
    assert req.preferred_time == ""


def test_signup_strips_whitespace(anon_client, db_session):
    """POST /signup обрезает пробелы."""
    from app.models import TrainingRequest

    r = anon_client.post("/signup", data={
        "first_name": "  Алексей  ",
        "last_name": "  Смирнов  ",
        "phone": "  +7  ",
        "pd_consent": "true",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "Ваша заявка принята" in r.text

    req = db_session.query(TrainingRequest).filter_by(first_name="Алексей").first()
    assert req is not None
    assert req.last_name == "Смирнов"
    assert req.phone == "+7"


def test_signup_success_page_has_home_link(anon_client):
    """Страница успеха содержит ссылку 'На главную'."""
    r = anon_client.post("/signup", data={
        "first_name": "UniqueHomeLink",
        "pd_consent": "true",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert 'href="/"' in r.text
    assert "На главную" in r.text


def test_signup_can_submit_multiple_times(anon_client, db_session):
    """Можно отправить несколько заявок — каждая сохраняется."""
    from app.models import TrainingRequest

    anon_client.post("/signup", data={"first_name": "First", "pd_consent": "true"}, follow_redirects=True)
    anon_client.post("/signup", data={"first_name": "Second", "pd_consent": "true"}, follow_redirects=True)

    assert db_session.query(TrainingRequest).filter_by(first_name="First").count() == 1
    assert db_session.query(TrainingRequest).filter_by(first_name="Second").count() == 1


def test_signup_preserves_created_at(anon_client, db_session):
    """Заявка сохраняет временную метку created_at."""
    from datetime import datetime
    from app.models import TrainingRequest

    before = datetime.now()
    anon_client.post("/signup", data={"first_name": "TimeTest", "pd_consent": "true"}, follow_redirects=True)
    after = datetime.now()

    req = db_session.query(TrainingRequest).filter_by(first_name="TimeTest").first()
    assert req is not None
    assert req.created_at is not None
    assert before <= req.created_at.replace(tzinfo=None) <= after


def test_signup_get_does_not_create_request(anon_client, db_session):
    """Простой GET /signup не создаёт запись."""
    from app.models import TrainingRequest

    before = db_session.query(TrainingRequest).count()
    anon_client.get("/signup")
    after = db_session.query(TrainingRequest).count()
    assert after == before


def test_signup_nav_link_exists(anon_client):
    """На главной странице есть ссылка 'Записаться' для анонима."""
    r = anon_client.get("/")
    assert r.status_code == 200
    assert 'Записаться' in r.text


def test_gallery_page_available(anon_client):
    """GET /gallery returns 200 with placeholders."""
    r = anon_client.get("/gallery")
    assert r.status_code == 200
    assert "Галерея" in r.text
    assert "gallery-photo" in r.text


def test_gallery_has_trainer_names(anon_client):
    """Gallery shows trainer names."""
    r = anon_client.get("/gallery")
    assert r.status_code == 200
    assert "Фото студии" in r.text
    assert "Тренировочный зал" in r.text


def test_gallery_nav_link_exists(anon_client):
    """Navigation has gallery link."""
    r = anon_client.get("/")
    assert "/gallery" in r.text
