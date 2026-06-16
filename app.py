"""
SUPERIOR CRM — точка входа.

Собирает FastAPI-приложение: монтирует статику, подключает роутеры,
выполняет инициализацию БД и seed-данные (только при прямом запуске).
"""

from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import database  # noqa: F401 — регистрирует Jinja2-фильтры
from models import Client, Slot  # seed-data models
from models import Booking, JournalEntry, TrainingNote  # re-export for tests (keep last)
from routes.clients import router as clients_router
from routes.schedule import router as schedule_router
from routes.slots import router as slots_router
from routes.program import router as program_router
from routes.journal import router as journal_router

import os as _os
app = FastAPI(title="SUPERIOR CRM")
_static_dir = _os.path.join(_os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# ---- Подключаем роутеры ----
app.include_router(journal_router)       # /, /journal, /subscriptions
app.include_router(clients_router)       # /clients, /clients/*
app.include_router(schedule_router)      # /schedule, /slot/{id}
app.include_router(slots_router)         # /slots/*, /slot/{id}/add|remove|complete
app.include_router(program_router)       # /slot/{id}/program

# ---- Инициализация БД (только при прямом запуске, не через Alembic) ----
if "alembic" not in __import__("sys").modules:
    from database import run_startup_migrations, SessionLocal

    run_startup_migrations()

    # Seed-данные для разработки
    db = SessionLocal()
    try:
        if db.query(Client).count() == 0:
            db.add_all([
                Client(first_name="Иван", last_name="Петров",
                       birth_year=1985, birth_place="Москва",
                       phone="+79990000001", name="Петров Иван", remaining_sessions=1),
                Client(first_name="Мария", last_name="Иванова",
                       birth_year=1990, birth_place="Санкт-Петербург",
                       phone="+79990000002", name="Иванова Мария", remaining_sessions=1),
                Client(first_name="Алексей", last_name="Сидоров",
                       birth_year=1988, birth_place="Казань",
                       phone="+79990000003", name="Сидоров Алексей", remaining_sessions=1),
            ])
            db.commit()

        if db.query(Slot).count() == 0:
            now = datetime.now()
            db.add_all([
                Slot(start_time=now + timedelta(hours=1), capacity=1),
                Slot(start_time=now + timedelta(hours=2), capacity=2),
                Slot(start_time=now + timedelta(hours=3), capacity=4),
            ])
            db.commit()
    finally:
        db.close()
