"""Тесты сессий: разные клиенты = разные сессии, независимость вкладок."""

import pytest
from fastapi.testclient import TestClient

from main import app
from app.database import get_db


@pytest.fixture()
def tab2(db_session):
    """Второй TestClient (симулирует вторую вкладку браузера) с той же БД."""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c


def test_two_tabs_have_independent_sessions(anon_client, tab2, db_session):
    """Две вкладки с разными учётками — профили не пересекаются.

    Tab 1: admin, Tab 2: client. После входа на Tab 2, Tab 1 всё ещё admin.
    """
    # === Tab 1: логинимся админом ===
    r = anon_client.post("/login", data={"login": "admin", "password": "admin"}, follow_redirects=False)
    assert r.status_code == 303

    r1 = anon_client.get("/profile")
    assert r1.status_code == 200
    assert "Администратор" in r1.text

    # === Tab 2: логинимся клиентом ===
    from app.models import Client as ClientModel
    from app.auth import hash_password

    c = ClientModel(first_name="Tab2", last_name="Client", phone="+70000000111",
                    remaining_sessions=3, login="tab2_user",
                    password_hash=hash_password("pass123"))
    db_session.add(c)
    db_session.commit()

    r2 = tab2.post("/login", data={"login": "tab2_user", "password": "pass123"}, follow_redirects=False)
    assert r2.status_code == 303

    r2_profile = tab2.get("/profile")
    assert r2_profile.status_code == 200
    assert "Tab2" in r2_profile.text

    # === Tab 1 всё ещё админ ===
    r1_again = anon_client.get("/profile")
    assert r1_again.status_code == 200
    assert "Администратор" in r1_again.text


def test_session_ids_differ_after_separate_logins(anon_client, tab2):
    """После входа в разных вкладках session_id разные."""
    tab1 = anon_client
    r1 = tab1.post("/login", data={"login": "admin", "password": "admin"}, follow_redirects=False)
    sid_admin = r1.cookies.get("sid")

    r2 = tab2.post("/login", data={"login": "trainer", "password": "trainer"}, follow_redirects=False)
    sid_trainer = r2.cookies.get("sid")

    assert sid_admin is not None
    assert sid_trainer is not None
    assert sid_admin != sid_trainer, "session_id должен быть разным для разных вкладок"


def test_old_session_survives_new_login(anon_client, tab2):
    """Старый session_id остаётся в БД после логина в другой вкладке."""
    tab1 = anon_client
    r1 = tab1.post("/login", data={"login": "admin", "password": "admin"}, follow_redirects=False)
    sid_admin = r1.cookies.get("sid")

    # Tab 2 логинится — это создаёт новый sid, но старый не удаляется
    tab2.post("/login", data={"login": "trainer", "password": "trainer"}, follow_redirects=False)

    # Tab 1 со своим sid — всё ещё админ
    r1_again = anon_client.get("/profile")
    assert r1_again.status_code == 200
    assert "Администратор" in r1_again.text


def test_logout_clears_session(anon_client):
    """После logout сессия очищается, профиль недоступен."""
    anon_client.post("/login", data={"login": "admin", "password": "admin"}, follow_redirects=False)

    r = anon_client.get("/profile")
    assert r.status_code == 200

    anon_client.post("/logout", follow_redirects=False)

    r2 = anon_client.get("/profile", follow_redirects=False)
    assert r2.status_code == 303
    assert "/login" in r2.headers.get("location", "")


def test_register_creates_new_session(anon_client):
    """После регистрации создаётся новая сессия, профиль доступен."""
    r = anon_client.post("/register", data={
        "login": "fresh_user", "password": "123",
        "first_name": "Fresh", "last_name": "User", "phone": "+70000000999",
    }, follow_redirects=False)
    assert r.status_code == 303

    r2 = anon_client.get("/profile")
    assert r2.status_code == 200
    assert "Fresh" in r2.text
