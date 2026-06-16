"""
SUPERIOR CRM — точка входа.

Собирает FastAPI-приложение: монтирует статику, подключает роутеры,
выполняет инициализацию БД и seed-данные (только при прямом запуске).
"""

from datetime import datetime, timedelta

import os as _os
import time as _time
import logging as _logging

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from starlette.middleware.sessions import SessionMiddleware

import app.database  # noqa: F401 — регистрирует Jinja2-фильтры
from app.logging_config import logger as _app_logger
from app.models import Client, Slot, Booking, JournalEntry, TrainingNote  # re-export + seed
from app.routes.clients import router as clients_router
from app.routes.schedule import router as schedule_router
from app.routes.slots import router as slots_router
from app.routes.program import router as program_router
from app.routes.journal import router as journal_router
from app.auth import router as auth_router
from app.auth import get_current_user
from app.timezone import now as tz_now

_log = _logging.getLogger("superior.request")
_trace_log = _logging.getLogger("superior.trace")

app = FastAPI(title="SUPERIOR CRM")

# Сессии (секретный ключ — из переменной окружения)
app.add_middleware(SessionMiddleware, secret_key=_os.getenv("SESSION_SECRET", "superior-dev-secret-key-change-in-prod"))
_static_dir = _os.path.join(_os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# ---- Request-логгер (метод, путь, статус, длительность) ----
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = _time.time()
    response = await call_next(request)
    duration = _time.time() - start
    _log.info("%s %s → %s (%.0fms)",
              request.method, request.url.path, response.status_code, duration * 1000)
    return response


# ---- Трассировка запросов (вкл через TRACE=1) ----
if _os.getenv("TRACE"):
    @app.middleware("http")
    async def trace_requests(request: Request, call_next):
        req_id = _os.urandom(4).hex()
        _trace_log.debug("[%s] >>> %s %s | headers: %s, query: %s",
                         req_id, request.method, request.url.path,
                         dict(request.headers), dict(request.query_params))
        body = await request.body()
        if body:
            _trace_log.debug("[%s] body: %s", req_id, body.decode(errors="replace")[:2000])
        start = _time.time()
        response = await call_next(request)
        duration = _time.time() - start
        _trace_log.debug("[%s] <<< %s (%.0fms) | headers: %s",
                         req_id, response.status_code, duration * 1000,
                         dict(response.headers))
        return response

# ---- Подключаем роутеры ----
app.include_router(auth_router)          # /login, /logout, /profile
app.include_router(journal_router)       # /, /journal, /subscriptions
app.include_router(clients_router)       # /clients, /clients/*
app.include_router(schedule_router)      # /schedule, /slot/{id}
app.include_router(slots_router)         # /slots/*, /slot/{id}/add|remove|complete
app.include_router(program_router)       # /slot/{id}/program



# ---- Инициализация БД (только при прямом запуске, не через Alembic) ----
if "alembic" not in __import__("sys").modules:
    from app.database import run_startup_migrations, SessionLocal

    run_startup_migrations()

    # Seed-данные для разработки
    from app.auth import hash_password

    db = SessionLocal()
    try:
        if db.query(Client).count() == 0:
            db.add_all([
                Client(first_name="Иван", last_name="Петров",
                       birth_year=1985, birth_place="Москва",
                       phone="+79990000001", name="Петров Иван", remaining_sessions=1,
                       login="client_1", password_hash=hash_password("client_1")),
                Client(first_name="Мария", last_name="Иванова",
                       birth_year=1990, birth_place="Санкт-Петербург",
                       phone="+79990000002", name="Иванова Мария", remaining_sessions=1,
                       login="client_2", password_hash=hash_password("client_2")),
                Client(first_name="Алексей", last_name="Сидоров",
                       birth_year=1988, birth_place="Казань",
                       phone="+79990000003", name="Сидоров Алексей", remaining_sessions=1,
                       login="client_3", password_hash=hash_password("client_3")),
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
