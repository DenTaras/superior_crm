import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure project root is on sys.path so `import app` works when pytest runs
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, Base, get_db


@pytest.fixture(scope="session")
def tmp_db_path(tmp_path_factory):
    p = tmp_path_factory.mktemp("data") / "test.db"
    return p


@pytest.fixture(scope="session")
def engine(tmp_db_path):
    path = tmp_db_path
    conn_str = f"sqlite:///{path}"
    engine = create_engine(conn_str, connect_args={"check_same_thread": False})
    # create tables
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine, db_session):
    # override dependency
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
