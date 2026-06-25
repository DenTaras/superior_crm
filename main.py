"""
SUPERIOR CRM — точка входа.

Собирает FastAPI-приложение: монтирует статику, подключает роутеры,
выполняет инициализацию БД и seed-данные (только при прямом запуске).
"""

from datetime import datetime, timedelta

import os as _os
import time as _time
import logging as _logging

# Загрузка .env (если есть) — ДО импорта app.database
if _os.getenv("CSRF_DISABLE") != "1":
    try:
        from dotenv import load_dotenv
        _dotenv_path = _os.path.join(_os.path.dirname(__file__), ".env")
        if _os.path.exists(_dotenv_path):
            load_dotenv(_dotenv_path, override=True)
    except ImportError:
        pass

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

import app.database  # noqa: F401 — регистрирует Jinja2-фильтры
from app.logging_config import logger as _app_logger
from app.models import Client, Slot, Booking, JournalEntry, TrainingNote  # re-export + seed
from app.routes.clients import router as clients_router
from app.routes.schedule import router as schedule_router
from app.routes.slots import router as slots_router
from app.routes.program import router as program_router
from app.smart_program import router as smart_program_router
from app.routes.journal import router as journal_router
from app.routes.signup import router as signup_router
from app.routes.sql_console import router as sql_router
from app.routes.exercises_api import router as exercises_api_router
from app.routes.budget import router as budget_router
from app.routes.dashboard import router as dashboard_router
from app.routes.nutrition import router as nutrition_router
from app.routes.nutrition2 import router as nutrition2_router
from app.routes.employees import router as employees_router
# from app.routes.payment import router as payment_router
# from app.routes.telegram import router as telegram_router
from app.auth import router as auth_router
from app.auth import get_current_user
from app.timezone import now as tz_now
from app.session import DbSessionMiddleware
from app.csrf import csrf_middleware

_log = _logging.getLogger("superior.request")
_trace_log = _logging.getLogger("superior.trace")

app = FastAPI(title="SUPERIOR CRM")

_static_dir = _os.path.join(_os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# Порядок middleware (от внешнего к внутреннему):
#   DbSessionMiddleware (самый внешний) → csrf_check → log → headers → роутер
# DbSessionMiddleware должен быть снаружи, чтобы request.session был доступен
# во всех внутренних middleware (особенно csrf_check).
app.add_middleware(DbSessionMiddleware)


# ---- CSRF-защита ----
@app.middleware("http")
async def csrf_check(request, call_next):
    from app.csrf import csrf_middleware as _csrf
    return await _csrf(request, call_next)


# ---- Content-Security-Policy (защита от XSS) ----
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "form-action 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


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
app.include_router(signup_router)        # /signup
app.include_router(sql_router)           # /sql
app.include_router(exercises_api_router) # /api/exercise-*
app.include_router(budget_router)        # /budget
app.include_router(dashboard_router)     # /dashboard
app.include_router(nutrition_router)      # /profile/nutrition
app.include_router(nutrition2_router)     # /profile/nutrition2
app.include_router(clients_router)       # /clients, /clients/*
app.include_router(schedule_router)      # /schedule, /slot/{id}
app.include_router(slots_router)         # /slots/*, /slot/{id}/add|remove|complete
app.include_router(program_router)       # /slot/{id}/program
app.include_router(smart_program_router) # /api/smart-program
app.include_router(employees_router)     # /employees
# if _os.getenv("DISABLE_PAYMENTS") != "1":
#     app.include_router(payment_router)       # /api/create-payment, /api/payment-callback
# if _os.getenv("DISABLE_TELEGRAM") != "1":
#     app.include_router(telegram_router)      # /tg-webhook



# ---- Инициализация БД (только при прямом запуске, не через Alembic) ----
if "alembic" not in __import__("sys").modules:
    from app.database import run_startup_migrations, SessionLocal

    run_startup_migrations()

    # Seed-данные для разработки
    from app.seed_data import seed_all

    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
