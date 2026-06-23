"""Настройка базы данных: engine, сессия, dependency get_db, утилиты;
   а также Jinja2 templates (общеприложение — здесь, чтобы избежать циклических импортов)."""

import os
from typing import Generator

from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text, inspect as sa_inspect
from sqlalchemy.orm import sessionmaker, Session

# Импортируем модели, чтобы они зарегистрировались на Base.metadata
from app.models import Base  # noqa: F401

# ---- Jinja2 templates (доступны всем роутам) ----
_templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=_templates_dir)


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

from app.timezone import localtime  # noqa: E402
templates.env.filters['localtime'] = localtime

# CSRF-токен для шаблонов (Markup — чтобы Jinja2 не экранировал HTML)
try:
    from markupsafe import Markup
except ImportError:
    from jinja2 import Markup
from app.csrf import get_csrf_token as _get_csrf
templates.env.globals['csrf_input'] = lambda request: Markup(
    f'<input type="hidden" name="_csrf_token" value="{_get_csrf(request)}" />'
)


# ---- Engine & Session ----
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///superior.db")

# Если для DATABASE_URL не установлен нужный драйвер (например, psycopg2),
# бесшумно падаем на SQLite. Это позволяет запускать pytest, не сбрасывая
# переменную окружения, когда PostgreSQL не запущен / не установлен драйвер.
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

try:
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
except ModuleNotFoundError:
    fallback_url = "sqlite:///superior.db"
    print(f"[WARN] Driver for {DATABASE_URL} not installed, falling back to {fallback_url}")
    DATABASE_URL = fallback_url
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

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
    except Exception as ex:
        print(f"[WARN] _get_table_columns({table_name!r}): {ex}")
        return []


def ensure_client_columns():
    """Добавить недостающие колонки в таблицу clients."""
    existing = _get_table_columns("clients")
    if not existing:
        return
    to_add = [
        ("first_name", "TEXT"), ("last_name", "TEXT"), ("patronymic", "TEXT"),
        ("birth_year", "INTEGER"), ("birth_place", "TEXT"), ("phone", "TEXT"),
        ("name", "TEXT"),
        ("height_cm", "INTEGER"), ("weight_kg", "INTEGER"), ("body_fat", "INTEGER"),
        ("photo_path", "TEXT"),
        ("hip_cm", "INTEGER"), ("waist_cm", "INTEGER"), ("chest_cm", "INTEGER"),
        ("shoulders_cm", "INTEGER"), ("biceps_cm", "INTEGER"),
        ("neck_cm", "INTEGER"), ("wrist_cm", "INTEGER"),
        ("skinfold_chest", "INTEGER"), ("skinfold_abdominal", "INTEGER"),
        ("skinfold_thigh", "INTEGER"), ("skinfold_triceps", "INTEGER"),
        ("skinfold_subscapular", "INTEGER"),
        ("sex", "TEXT"),
        ("goal", "TEXT"),
        ("activity_level", "TEXT"),
        ("pd_consent_given", "BOOLEAN"),
        ("pd_consent_at", "TIMESTAMP"),
    ]
    with engine.connect() as conn:
        for col, coltype in to_add:
            if col not in existing:
                try:
                    conn.execute(text(f"ALTER TABLE clients ADD COLUMN {col} {coltype}"))
                except Exception as ex:
                    print(f"[WARN] ALTER TABLE clients ADD {col}: {ex}")


def ensure_journal_columns():
    """Добавить колонку comments в таблицу journal."""
    existing = _get_table_columns("journal")
    if not existing:
        return
    if 'comments' not in existing:
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE journal ADD COLUMN comments TEXT"))
            except Exception as ex:
                print(f"[WARN] ALTER TABLE journal ADD comments: {ex}")


def ensure_subscription_purchase_columns():
    """Добавить колонки refunded/refunded_at в subscription_purchases."""
    existing = _get_table_columns("subscription_purchases")
    if not existing:
        return
    with engine.connect() as conn:
        if 'refunded' not in existing:
            try:
                conn.execute(text("ALTER TABLE subscription_purchases ADD COLUMN refunded BOOLEAN DEFAULT 0"))
            except Exception as ex:
                print(f"[WARN] ALTER TABLE subscription_purchases ADD refunded: {ex}")
        if 'refunded_at' not in existing:
            try:
                conn.execute(text("ALTER TABLE subscription_purchases ADD COLUMN refunded_at TIMESTAMP"))
            except Exception as ex:
                print(f"[WARN] ALTER TABLE subscription_purchases ADD refunded_at: {ex}")


def ensure_anthropometry_log_columns():
    """Добавить новые колонки в anthropometry_log (если таблица уже существует)."""
    existing = _get_table_columns("anthropometry_log")
    if not existing:
        return
    to_add = [
        ("neck_cm", "INTEGER"), ("wrist_cm", "INTEGER"),
        ("skinfold_chest", "INTEGER"), ("skinfold_abdominal", "INTEGER"),
        ("skinfold_thigh", "INTEGER"), ("skinfold_triceps", "INTEGER"),
        ("skinfold_subscapular", "INTEGER"),
    ]
    with engine.connect() as conn:
        for col, coltype in to_add:
            if col not in existing:
                try:
                    conn.execute(text(f"ALTER TABLE anthropometry_log ADD COLUMN {col} {coltype}"))
                except Exception as ex:
                    print(f"[WARN] ALTER TABLE anthropometry_log ADD {col}: {ex}")


def ensure_meal_templates_columns():
    """Добавить колонки ingredients/recipe в meal_templates."""
    existing = _get_table_columns("meal_templates")
    if not existing:
        return
    with engine.connect() as conn:
        if 'ingredients' not in existing:
            try:
                conn.execute(text("ALTER TABLE meal_templates ADD COLUMN ingredients TEXT"))
            except Exception as ex:
                print(f"[WARN] ALTER TABLE meal_templates ADD ingredients: {ex}")
        if 'recipe' not in existing:
            try:
                conn.execute(text("ALTER TABLE meal_templates ADD COLUMN recipe TEXT"))
            except Exception as ex:
                print(f"[WARN] ALTER TABLE meal_templates ADD recipe: {ex}")
        if 'course' not in existing:
            try:
                conn.execute(text("ALTER TABLE meal_templates ADD COLUMN course TEXT"))
            except Exception as ex:
                print(f"[WARN] ALTER TABLE meal_templates ADD course: {ex}")
    # Заполняем course для существующих записей (main по умолчанию)
    from app.seed_meals import _infer_course
    from sqlalchemy.orm import sessionmaker
    _s = sessionmaker(bind=engine)()
    try:
        from app.models import MealTemplate
        for mt in _s.query(MealTemplate).filter(MealTemplate.course.is_(None)).all():
            mt.course = _infer_course(mt.meal_type, mt.name)
            _s.add(mt)
        _s.commit()
    finally:
        _s.close()


def ensure_training_request_columns():
    """Добавить колонки pd_consent в training_requests."""
    existing = _get_table_columns("training_requests")
    if not existing:
        return
    with engine.connect() as conn:
        for col in ("pd_consent", "pd_consent_at"):
            if col not in existing:
                try:
                    coltype = "BOOLEAN" if col == "pd_consent" else "TIMESTAMP"
                    conn.execute(text(f"ALTER TABLE training_requests ADD COLUMN {col} {coltype}"))
                except Exception as ex:
                    print(f"[WARN] ALTER TABLE training_requests ADD {col}: {ex}")


def ensure_payment_columns():
    """Добавить колонки в payments (если таблица уже существует)."""
    existing = _get_table_columns("payments")
    if not existing:
        return
    with engine.connect() as conn:
        for col in ("provider_payment_id",):
            if col not in existing:
                try:
                    conn.execute(text(f"ALTER TABLE payments ADD COLUMN {col} TEXT"))
                except Exception as ex:
                    print(f"[WARN] ALTER TABLE payments ADD {col}: {ex}")


def ensure_employee_columns():
    """Добавить колонку regional_coefficient в employees."""
    existing = _get_table_columns("employees")
    if not existing:
        return
    with engine.connect() as conn:
        if "regional_coefficient" not in existing:
            try:
                conn.execute(text("ALTER TABLE employees ADD COLUMN regional_coefficient INTEGER DEFAULT 100"))
            except Exception as ex:
                print(f"[WARN] ALTER TABLE employees ADD regional_coefficient: {ex}")


def run_startup_migrations():
    """Создать таблицы и выполнить runtime-миграции (только для прямого запуска)."""
    Base.metadata.create_all(engine)
    ensure_client_columns()
    ensure_journal_columns()
    ensure_subscription_purchase_columns()
    ensure_anthropometry_log_columns()
    ensure_meal_templates_columns()
    ensure_training_request_columns()
    ensure_employee_columns()
    ensure_payment_columns()

    # Добавить недостающие упражнения из seed
    from app.seed_exercises import ensure_exercises
    from sqlalchemy.orm import sessionmaker
    _s = sessionmaker(bind=engine)()
    try:
        ensure_exercises(_s)
    finally:
        _s.close()

    # Seed шаблонов питания
    from app.seed_meals import seed_meals
    _s2 = sessionmaker(bind=engine)()
    try:
        seed_meals(_s2)
    finally:
        _s2.close()

    # Seed продуктов и связей
    from app.seed_products import seed_products
    _s3 = sessionmaker(bind=engine)()
    try:
        seed_products(_s3)
    finally:
        _s3.close()
