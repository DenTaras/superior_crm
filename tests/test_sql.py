"""Тесты SQL-консоли (только admin)."""


def test_sql_page_requires_admin(client, anon_client):
    """GET /sql — только для админа."""
    r_anon = anon_client.get("/sql", follow_redirects=False)
    assert r_anon.status_code == 303  # редирект на login

    r_admin = client.get("/sql")
    assert r_admin.status_code == 200
    assert "SQL-консоль" in r_admin.text


def test_sql_page_shows_form(client):
    """GET /sql показывает форму запроса и заметки."""
    r = client.get("/sql")
    assert r.status_code == 200
    assert "SQL-запрос" in r.text
    assert "Выполнить" in r.text
    assert "csrf_token" in r.text
    assert "Заметки" in r.text


def test_sql_execute_select(client):
    """POST /sql с SELECT возвращает результаты."""
    r = client.post("/sql", data={"query": "SELECT 1 AS num, 'hello' AS msg;"}, follow_redirects=True)
    assert r.status_code == 200
    assert "num" in r.text or "msg" in r.text
    assert "1" in r.text
    assert "hello" in r.text


def test_sql_execute_delete(client):
    """POST /sql с DELETE выполняется, показывает количество затронутых строк."""
    r = client.post("/sql", data={"query": "DELETE FROM clients WHERE 1=0;"}, follow_redirects=True)
    assert r.status_code == 200
    assert "Затронуто строк" in r.text
    assert "0" in r.text


def test_sql_rejects_empty(client):
    """POST /sql с пустым запросом — ошибка на странице."""
    r = client.post("/sql", data={"query": ""}, follow_redirects=True)
    assert r.status_code == 200
    assert "пустым" in r.text


def test_sql_shows_error_on_bad_query(client):
    """POST /sql с невалидным SQL — ошибка."""
    r = client.post("/sql", data={"query": "SELECT FROM nowhere;"}, follow_redirects=True)
    assert r.status_code == 200
    assert "Ошибка" in r.text


def test_sql_requires_auth(anon_client):
    """POST /sql без авторизации — редирект."""
    r = anon_client.post("/sql", data={"query": "SELECT 1;"}, follow_redirects=False)
    assert r.status_code == 303


def test_sql_shows_row_count(client, db_session):
    """После запроса показывается количество строк."""
    from app.models import Client
    c = Client(first_name="SQL", last_name="Test", phone="+70000000999")
    db_session.add(c)
    db_session.commit()

    r = client.post("/sql", data={"query": "SELECT * FROM clients LIMIT 5;"}, follow_redirects=True)
    assert r.status_code == 200
    assert "Результат" in r.text
    assert "SQL" in r.text
