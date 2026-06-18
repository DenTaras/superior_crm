"""Аутентификация и роли.

Встроенные учётные записи:
  admin / admin       — администратор (из ADMIN_LOGIN/ADMIN_PASSWORD)
  trainer / trainer   — тренер (из TRAINER_LOGIN/TRAINER_PASSWORD)
  client_1 / client_1 — клиент (логин/пароль из БД)
"""

import os
import hashlib
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db, templates
from app.models import Client
from app.ratelimit import check_rate_limit, clear_rate_limit
from app.pricing import slot_time_slot
from app.timezone import now as tz_now

router = APIRouter()

ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
TRAINER_LOGIN = os.getenv("TRAINER_LOGIN", "trainer")
TRAINER_PASSWORD = os.getenv("TRAINER_PASSWORD", "trainer")

# Параметры PBKDF2
_PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    """Хеширование пароля через PBKDF2-SHA256 с уникальной солью.

    Формат: алгоритм$итерации$соль$хеш
    """
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS)
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt}${pwd_hash.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Проверить пароль против хранимого хеша (поддерживает legacy SHA256)."""
    if stored.startswith("pbkdf2$"):
        parts = stored.split("$")
        if len(parts) != 4:
            return False
        _, iterations, salt, expected_hex = parts
        try:
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
            return actual.hex() == expected_hex
        except Exception:
            return False
    # legacy: старый формат sha256 с константной солью
    return stored == hashlib.sha256(f"superior_salt_{password}".encode()).hexdigest()


def get_current_user(request: Request) -> Optional[dict]:
    """Вернуть информацию о текущем пользователе из сессии."""
    return request.session.get("user")


def require_role(*roles: str):
    """Dependency — проверяет, что пользователь авторизован и имеет одну из ролей."""
    def dependency(request: Request):
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=303, detail="/login", headers={"Location": "/login"})
        if user.get("role") not in roles:
            raise HTTPException(status_code=303, detail="/", headers={"Location": "/"})
        return user
    return dependency


# ---- Страницы ----


@router.get("/login")
def login_page(request: Request):
    """Форма входа."""
    if get_current_user(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={})


@router.post("/login")
def login_post(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Обработка входа для всех пользователей."""
    # Rate limit: 5 попыток в минуту на логин
    allowed, remaining = check_rate_limit(f"login:{login}")
    if not allowed:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Слишком много попыток. Попробуйте через минуту."},
            status_code=429,
        )

    # admin
    if login == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        clear_rate_limit(f"login:{login}")
        request.session.regenerate_id()
        request.session["user"] = {"role": "admin", "name": "Администратор"}
        return RedirectResponse("/", status_code=303)

    # trainer
    if login == TRAINER_LOGIN and password == TRAINER_PASSWORD:
        clear_rate_limit(f"login:{login}")
        request.session.regenerate_id()
        request.session["user"] = {"role": "trainer", "name": "Тренер"}
        return RedirectResponse("/", status_code=303)

    # client — проверка по БД
    client = db.query(Client).filter(Client.login == login).first()
    if client and client.password_hash and verify_password(password, client.password_hash):
        clear_rate_limit(f"login:{login}")
        request.session.regenerate_id()
        request.session["user"] = {
            "role": "client",
            "name": client.fio(),
            "client_id": client.id,
        }
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Неверный логин или пароль"},
        status_code=403,
    )


@router.get("/register")
def register_page(request: Request):
    """Форма регистрации нового клиента."""
    return templates.TemplateResponse(request=request, name="register.html", context={})


@router.post("/register")
def register_post(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(""),
    phone: str = Form(""),
    db: Session = Depends(get_db),
):
    """Регистрация нового клиента."""
    # проверяем, что логин уникален
    existing = db.query(Client).filter(Client.login == login).first()
    if existing:
        return templates.TemplateResponse(
            request=request, name="register.html",
            context={"error": "Логин уже занят"},
            status_code=403,
        )

    client = Client(
        login=login,
        password_hash=hash_password(password),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        phone=phone.strip(),
        name=f"{last_name.strip()} {first_name.strip()}".strip(),
    )
    db.add(client)
    db.flush()

    # Пробное занятие как абонемент
    from app.models import SubscriptionPurchase
    purchase = SubscriptionPurchase(
        client_id=client.id,
        time_slot="-",
        format_name="-",
        # "-" — универсальный формат (подходит для любого слота)
        package_size=1,
        price=0,
        remaining=1,
    )
    db.add(purchase)
    db.commit()

    request.session.regenerate_id()
    request.session["user"] = {
        "role": "client",
        "name": client.fio(),
        "client_id": client.id,
    }
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    """Выход."""
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/profile")
def profile_page(request: Request, db: Session = Depends(get_db)):
    """Личный кабинет."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    if user["role"] == "client":
        client_id = user.get("client_id")
        c = db.get(Client, client_id)
        bookings = []
        journal_entries = []
        strength_data = []
        booked_by_ts: dict[str, int] = {}
        if c:
            from app.models import Booking, Slot, JournalEntry
            import json

            # Будущие и активные бронирования
            rows = (
                db.query(Booking, Slot)
                .join(Slot, Booking.slot_id == Slot.id)
                .filter(Booking.client_id == client_id)
                .order_by(Slot.start_time.desc())
                .all()
            )
            bookings = [{"slot_time": s.start_time} for b, s in rows]

            # История завершённых тренировок из журнала
            cid_str = str(client_id)
            c_name = c.fio()
            raw_entries = (
                db.query(JournalEntry)
                .filter(JournalEntry.clients.contains(c_name))
                .order_by(JournalEntry.created_at.desc())
                .limit(50)
                .all()
            )
            for je in raw_entries:
                plan = ""
                if je.comments:
                    try:
                        cmap = json.loads(je.comments)
                        plan = cmap.get(cid_str, "")
                    except Exception:
                        pass
                journal_entries.append({
                    "entry": je,
                    "plan": plan,
                })

            # Силовые показатели
            from app.strength import collect_strength_data, enrich_with_rank, compute_standards_table
            from app.models import SubscriptionPurchase
            bw = c.weight_kg or 0
            strength_data = collect_strength_data(db, client_id)
            strength_data = enrich_with_rank(strength_data, "male", bw)
            standards_table = compute_standards_table("male", bw) if bw > 0 else []

            # Будущие брони по time_slot
            from app.models import Slot as SlotModel
            future_slots = (
                db.query(SlotModel)
                .join(Booking, Booking.slot_id == SlotModel.id)
                .filter(Booking.client_id == client_id, SlotModel.start_time >= tz_now())
                .all()
            )
            for sl in future_slots:
                ts = slot_time_slot(sl.start_time)
                booked_by_ts[ts] = booked_by_ts.get(ts, 0) + 1

            # Активные абонементы (группируем одинаковые format_name+time_slot)
            active_purchases_raw = (
                db.query(SubscriptionPurchase)
                .filter(
                    SubscriptionPurchase.client_id == client_id,
                    SubscriptionPurchase.remaining > 0,
                )
                .order_by(SubscriptionPurchase.created_at.asc())
                .all()
            )
            grouped: dict[tuple[str, str], int] = {}
            for p in active_purchases_raw:
                key = (p.format_name, p.time_slot)
                grouped[key] = grouped.get(key, 0) + p.remaining

            active_purchases = [
                {"format_name": k[0], "time_slot": k[1], "remaining": v}
                for k, v in sorted(grouped.items())
            ]

        total_remaining = sum(p["remaining"] for p in active_purchases) if c else 0

        return templates.TemplateResponse(
            request=request, name="user.html",
            context={
                "user": user, "client": c,
                "bookings": bookings, "journal_entries": journal_entries,
                "strength_data": strength_data,
                "standards_table": standards_table,
                "active_purchases": active_purchases,
                "booked_by_time_slot": booked_by_ts,
                "total_remaining": total_remaining,
            },
        )

    # admin / trainer
    from app.models import Client as ClientModel
    from app.models import Slot as SlotModel, JournalEntry
    total_clients = db.query(ClientModel).count()
    total_slots = db.query(SlotModel).count()
    total_journal = db.query(JournalEntry).count()
    return templates.TemplateResponse(
        request=request, name="user.html",
        context={
            "user": user,
            "total_clients": total_clients,
            "total_slots": total_slots,
            "total_journal": total_journal,
        },
    )
