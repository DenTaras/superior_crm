"""Security-тесты: проверяют, что уязвимости действительно исправлены."""

import os
import re
import time
import html as html_mod
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from main import app
from app.database import get_db


# ===== XSS =====


def test_xss_in_notes_json_is_sanitized(client, db_session):
    """XSS через заметку тренировки — тег </script> экранирован."""
    from app.models import Client, Slot, Booking, TrainingNote

    now = datetime.now().replace(second=0, microsecond=0)
    c = Client(first_name="XSS", last_name="Test", phone="+70000000900", name="XSS Test")
    s = Slot(start_time=now + timedelta(days=1, hours=5), capacity=2)
    db_session.add_all([c, s])
    db_session.commit()
    b = Booking(client_id=c.id, slot_id=s.id)
    db_session.add(b)
    db_session.commit()

    payload = '</script><script>alert("xss")</script>'
    note = TrainingNote(slot_id=s.id, client_id=c.id, text=payload)
    db_session.add(note)
    db_session.commit()

    r = client.get(f"/slot/{s.id}/program")
    assert r.status_code == 200

    # </script> не должен быть в неэкранированном виде внутри script-блока
    # после replace: </script> → <\/script>
    assert "\\u003c/script\\u003e" in r.text or "<\\/script>" in r.text or "&lt;/script&gt;" in r.text


def test_xss_in_client_name_is_escaped(client, db_session):
    """XSS-попытка в имени клиента экранируется Jinja2."""
    from app.models import Client

    payload = "<script>alert(1)</script>"
    c = Client(first_name=payload, last_name="XSS", phone="+70000000901", name=payload)
    db_session.add(c)
    db_session.commit()

    r = client.get("/clients")
    assert r.status_code == 200
    assert payload not in r.text or "&lt;script&gt;" in r.text


# ===== ХЕШИРОВАНИЕ ПАРОЛЕЙ =====


def test_password_hash_format():
    """Новый хеш пароля в формате pbkdf2$итерации$соль$хеш."""
    from app.auth import hash_password

    h = hash_password("test123")
    parts = h.split("$")
    assert len(parts) == 4
    assert parts[0] == "pbkdf2"
    assert parts[1].isdigit()
    assert len(parts[2]) == 32  # 16 байт соли = 32 hex
    assert len(parts[3]) == 64  # SHA256 = 64 hex


def test_verify_password_works():
    """Проверка пароля работает для нового и legacy формата."""
    from app.auth import hash_password, verify_password

    # новый формат
    h = hash_password("secret")
    assert verify_password("secret", h)
    assert not verify_password("wrong", h)

    # legacy формат
    import hashlib
    legacy = hashlib.sha256("superior_salt_oldpass".encode()).hexdigest()
    assert verify_password("oldpass", legacy)
    assert not verify_password("wrong", legacy)


# ===== CSRF =====


def test_csrf_missing_token_returns_403(anon_client, db_session):
    """POST без CSRF-токена возвращает 403 (при включённой защите)."""
    if os.getenv("CSRF_DISABLE") == "1":
        pytest.skip("CSRF отключён в тестовом окружении")

    # создаём клиента с CSRF-токеном через GET
    anon_client.get("/login")

    # POST без CSRF-токена
    r = anon_client.post("/login", data={"login": "admin", "password": "admin"}, follow_redirects=False)
    assert r.status_code == 403


def test_csrf_with_valid_token_succeeds(anon_client):
    """POST с корректным CSRF-токеном проходит."""
    if os.getenv("CSRF_DISABLE") == "1":
        pytest.skip("CSRF отключён в тестовом окружении")

    # получаем токен
    r = anon_client.get("/login")
    # извлекаем из формы
    match = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    assert match, "CSRF-токен не найден в форме"
    token = match.group(1)

    r = anon_client.post("/login", data={
        "login": "admin", "password": "admin",
        "_csrf_token": token,
    }, follow_redirects=False)
    assert r.status_code == 303


# ===== RATE LIMITING =====


def test_rate_limit_blocks_excessive_attempts(anon_client):
    """Более 5 попыток входа в минуту блокируются."""
    for i in range(5):
        r = anon_client.post("/login", data={
            "login": "rate_test_user", "password": "wrong",
        }, follow_redirects=False)
        # первые 5 — 403 (неверный пароль)
        assert r.status_code == 403

    # 6-я попытка — rate limit
    r = anon_client.post("/login", data={
        "login": "rate_test_user", "password": "wrong",
    }, follow_redirects=False)
    assert r.status_code == 429
    assert "Слишком много" in r.text


def test_rate_limit_resets_after_success(anon_client, db_session):
    """После успешного входа счётчик для этого логина сбрасывается."""
    from app.models import Client as ClientModel
    from app.auth import hash_password

    login = "ratelimit_user"
    c = ClientModel(first_name="Rate", last_name="Limit", phone="+70000000999",
                    login=login, password_hash=hash_password("correct_pass"))
    db_session.add(c)
    db_session.commit()

    # 3 неудачных попытки
    for i in range(3):
        anon_client.post("/login", data={
            "login": login, "password": "wrong",
        }, follow_redirects=False)

    # успешный вход
    r = anon_client.post("/login", data={
        "login": login, "password": "correct_pass",
    }, follow_redirects=False)
    assert r.status_code == 303

    # счётчик сброшен — можно снова пробовать
    for i in range(3):
        r = anon_client.post("/login", data={
            "login": login, "password": "wrong",
        }, follow_redirects=False)
        assert r.status_code == 403


# ===== CSP HEADERS =====


def test_csp_headers_present(anon_client):
    """Ответы содержат заголовки безопасности."""
    r = anon_client.get("/login")
    assert "Content-Security-Policy" in r.headers
    assert "X-Content-Type-Options" in r.headers
    assert "X-Frame-Options" in r.headers
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert "form-action 'self'" in r.headers["Content-Security-Policy"]


def test_csp_blocks_external_forms():
    """CSP form-action не позволяет отправлять формы на внешние домены."""
    r = TestClient(app).get("/login")
    csp = r.headers.get("Content-Security-Policy", "")
    assert "form-action 'self'" in csp
    # нет whitelist-ов внешних доменов
    assert "form-action https://" not in csp
