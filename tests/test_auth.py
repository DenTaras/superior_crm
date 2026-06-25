"""Тесты аутентификации и ролей."""

from app.auth import hash_password


def test_login_page_available(anon_client):
    """Страница /login доступна без авторизации."""
    r = anon_client.get("/login")
    assert r.status_code == 200
    assert "Логин" in r.text
    assert "Пароль" in r.text


def test_admin_login(anon_client):
    """Вход админа: редирект на /, профиль доступен."""
    r = anon_client.post("/login", data={"login": "admin", "password": "admin"}, follow_redirects=False)
    assert r.status_code == 303

    r2 = anon_client.get("/profile")
    assert r2.status_code == 200
    assert "Администратор" in r2.text


def test_trainer_login(anon_client):
    """Вход тренера."""
    r = anon_client.post("/login", data={"login": "trainer", "password": "trainer"}, follow_redirects=False)
    assert r.status_code == 303

    r2 = anon_client.get("/profile")
    assert r2.status_code == 200
    assert "Тренер" in r2.text


def test_client_login(anon_client, db_session):
    """Вход клиента по логину/паролю."""
    from app.models import Client as ClientModel

    c = ClientModel(first_name="Auth", last_name="Client", phone="+70000000999",
                    login="test_client",
                    password_hash=hash_password("pass123"))
    db_session.add(c)
    db_session.commit()

    r = anon_client.post("/login", data={"login": "test_client", "password": "pass123"}, follow_redirects=False)
    assert r.status_code == 303

    r2 = anon_client.get("/profile")
    assert r2.status_code == 200
    assert "Auth" in r2.text
    assert "3" in r2.text


def test_invalid_login(anon_client):
    """Неверные данные — страница логина с ошибкой."""
    r = anon_client.post("/login", data={"login": "wrong", "password": "wrong"}, follow_redirects=False)
    assert r.status_code == 403
    assert "Неверный" in r.text


def test_logout(client):
    """После выхода профиль недоступен."""
    # client уже авторизован как admin (фикстура)
    r = client.post("/logout", follow_redirects=False)
    assert r.status_code == 303

    r2 = client.get("/profile", follow_redirects=False)
    assert r2.status_code == 303
    assert "/login" in r2.headers.get("location", "")


def test_register_disabled(anon_client):
    """Регистрация отключена — /register возвращает 404."""
    r = anon_client.post("/register", data={
        "login": "new_user", "password": "pass",
        "first_name": "New", "last_name": "User", "phone": "+70000000123",
        "pd_consent": "true",
    }, follow_redirects=False)
    assert r.status_code == 404

    r2 = anon_client.get("/register")
    assert r2.status_code == 404


def test_register_duplicate_login(anon_client, db_session):
    """Регистрация отключена — дубликат логина не проверяется."""
    from app.models import Client as ClientModel
    from app.auth import hash_password

    c = ClientModel(first_name="Dup", login="dup_user",
                    password_hash=hash_password("x"))
    db_session.add(c)
    db_session.commit()

    r = anon_client.post("/register", data={
        "login": "dup_user", "password": "x",
        "first_name": "Dup2", "last_name": "", "phone": "",
        "pd_consent": "true",
    }, follow_redirects=False)
    assert r.status_code == 404
