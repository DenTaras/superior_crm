import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Отключаем CSRF для тестов (токен проверяется отдельными тестами)
os.environ["CSRF_DISABLE"] = "1"

# Ensure project root is on sys.path so `import app` works when pytest runs
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from main import app
from app.models import Base
from app.database import get_db
from app.session import set_session_engine


@pytest.fixture(scope="session")
def tmp_db_path(tmp_path_factory):
    """Создаёт временный путь к sqlite файлу для сессии тестов."""
    p = tmp_path_factory.mktemp("data") / "test.db"
    return p


@pytest.fixture(scope="session")
def engine(tmp_db_path):
    """Инициализирует SQLAlchemy engine, использующий временную базу для тестов.

    Создаёт все таблицы на этом engine и возвращает объект engine.
    """
    path = tmp_db_path
    conn_str = f"sqlite:///{path}"
    engine = create_engine(conn_str, connect_args={"check_same_thread": False})
    # create tables
    Base.metadata.create_all(engine)
    # перенаправляем сессии в ту же БД
    set_session_engine(engine)
    return engine


@pytest.fixture()
def db_session(engine):
    """Фикстура сессии базы данных для каждого теста.

    Возвращает активную `Session` и закрывает её по завершении теста.
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine, db_session):
    """Фикстура тест-клиента FastAPI, авторизованного как админ.

    Переопределяет `get_db` так, чтобы маршруты использовали `db_session`.
    Возвращает контекстный `TestClient` из `fastapi.testclient`.
    """
    # override dependency
    def override_get_db():
        """Генератор, возвращающий фиктивную сессию БД для использования в тестах."""
        db = db_session
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        c.post("/login", data={"login": "admin", "password": "admin"}, follow_redirects=False)
        yield c


@pytest.fixture()
def anon_client(engine, db_session):
    """Тест-клиент без авторизации (для тестов логина)."""
    def override_get_db():
        db = db_session
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c
