"""Настройка базы данных: engine, сессия, dependency get_db, утилиты;
   а также Jinja2 templates (общеприложение — здесь, чтобы избежать циклических импортов)."""

import os
from typing import Generator

from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text, inspect as sa_inspect
from sqlalchemy.orm import sessionmaker, Session

# Импортируем модели, чтобы они зарегистрировались на Base.metadata
from models import Base  # noqa: F401

# ---- Jinja2 templates (доступны всем роутам) ----
templates = Jinja2Templates(directory="templates")


def format_phone(value: str) -> str:
    """+79990000001 → +7 999 000 00 01"""
    if not value:
        return ""
    s = ''.join(ch for ch in value if ch.isdigit())
    if len(s) == 11 and s.startswith('7'):
        return f"+7 {s[1:4]} {s[4:7]} {s[7:9]} {s[9:11]}"
    if len(s) >= 10:
        return f"+{s[:-10]} {s[-10:-7]} {s[-7:-4]} {s[-4:-2]} {s[-2:]}"
    return value


templates.env.filters['format_phone'] = format_phone


# ---- Engine & Session ----
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///superior.db")
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — возвращает сессию БД и закрывает её после запроса."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---- Миграционные утилиты (runtime ALTER TABLE для локальной разработки) ----

def _get_table_columns(table_name: str) -> list:
    """Вернуть список имён колонок таблицы (через SQLAlchemy Inspector)."""
    try:
        inspector = sa_inspect(engine)
        return [col["name"] for col in inspector.get_columns(table_name)]
    except Exception:
        return []


def ensure_client_columns():
    """Добавить недостающие колонки в таблицу clients."""
    existing = _get_table_columns("clients")
    if not existing:
        return
    to_add = [
        ("first_name", "TEXT"), ("last_name", "TEXT"), ("patronymic", "TEXT"),
        ("birth_year", "INTEGER"), ("birth_place", "TEXT"), ("phone", "TEXT"),
        ("name", "TEXT"), ("remaining_sessions", "INTEGER DEFAULT 1"),
    ]
    with engine.connect() as conn:
        for col, coltype in to_add:
            if col not in existing:
                try:
                    conn.execute(text(f"ALTER TABLE clients ADD COLUMN {col} {coltype}"))
                except Exception:
                    pass


def ensure_journal_columns():
    """Добавить колонку comments в таблицу journal."""
    existing = _get_table_columns("journal")
    if not existing:
        return
    if 'comments' not in existing:
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE journal ADD COLUMN comments TEXT"))
            except Exception:
                pass


def run_startup_migrations():
    """Создать таблицы и выполнить runtime-миграции (только для прямого запуска)."""
    Base.metadata.create_all(engine)
    ensure_client_columns()
    ensure_journal_columns()

    with engine.connect() as conn:
        try:
            conn.execute(
                text("UPDATE clients SET remaining_sessions = 1 "
                     "WHERE remaining_sessions IS NULL OR remaining_sessions = 0")
            )
        except Exception:
            pass
