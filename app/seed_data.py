"""Seed-данные для разработки: клиенты, слоты, сотрудники.

Запускается автоматически при старте main.py (только если таблицы пустые).
Можно также запустить вручную:
  python -c "from app.seed_data import seed_all; from app.database import SessionLocal; seed_all(SessionLocal())"
"""

from datetime import datetime, timedelta

from app.auth import hash_password
from app.models import Client, Slot, SubscriptionPurchase, Employee
from app.seed_exercises import seed_exercises


def seed_clients(db):
    """Создать тестовых клиентов, если их нет."""
    if db.query(Client).count() > 0:
        return
    clients_data = [
        Client(first_name="Иван", last_name="Pетров",
               birth_year=1985, birth_place="Москва",
               phone="+79990000001", name="Петров Иван",
               login="client_1", password_hash=hash_password("client_1")),
        Client(first_name="Мария", last_name="Иванова",
               birth_year=1990, birth_place="Санкт-Петербург",
               phone="+79990000002", name="Иванова Мария",
               login="client_2", password_hash=hash_password("client_2")),
        Client(first_name="Алексей", last_name="Сидоров",
               birth_year=1988, birth_place="Казань",
               phone="+79990000003", name="Сидоров Алексей",
               login="client_3", password_hash=hash_password("client_3")),
        Client(first_name="Денис", last_name="Тарасов",
               birth_year=1994, birth_place="Омск",
               phone="+79990000004", name="Тарасов Денис",
               login="client_4", password_hash=hash_password("client_4")),
    ]
    db.add_all(clients_data)
    db.flush()
    for cl in clients_data:
        db.add(SubscriptionPurchase(
            client_id=cl.id, time_slot="-", format_name="-",
            package_size=1, price=0, remaining=1,
        ))
    db.commit()


def seed_slots(db):
    """Создать тестовые слоты, если их нет."""
    if db.query(Slot).count() > 0:
        return
    now = datetime.now()
    db.add_all([
        Slot(start_time=now + timedelta(hours=1), capacity=1),
        Slot(start_time=now + timedelta(hours=2), capacity=2),
        Slot(start_time=now + timedelta(hours=3), capacity=4),
    ])
    db.commit()


def seed_employees(db):
    """Создать тестовых сотрудников, если их нет."""
    if db.query(Employee).count() > 0:
        return
    db.add_all([
        Employee(first_name="Анна", last_name="Директорова",
                 position="director", login="admin",
                 password_hash=hash_password("admin"),
                 salary_type="fixed+dividends",
                 salary_amount=120_000, regional_coefficient=115, dividend_percent=50),
        Employee(first_name="Пётр", last_name="Тренеров",
                 position="trainer", login="trainer",
                 password_hash=hash_password("trainer"),
                 salary_type="fixed+bonus",
                 salary_amount=40_000, regional_coefficient=115, bonus_percent=10),
    ])
    db.commit()


def seed_all(db):
    """Запустить все seed-функции."""
    seed_exercises(db)
    seed_clients(db)
    seed_slots(db)
    seed_employees(db)
