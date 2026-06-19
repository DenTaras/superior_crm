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
            from app.models import Booking, Slot, JournalEntry, SubscriptionPurchase
            from app.pricing import format_from_capacity
            import json

            # Будущие и активные бронирования
            rows = (
                db.query(Booking, Slot)
                .join(Slot, Booking.slot_id == Slot.id)
                .filter(Booking.client_id == client_id)
                .order_by(Slot.start_time.desc())
                .all()
            )
            bookings = [{"slot_time": s.start_time, "slot_id": s.id, "slot": s} for b, s in rows]

            # Доступные для бронирования слоты (будущие, не заполненные, с подходящим пакетом)
            from sqlalchemy import func, Integer, case
            from app.pricing import slot_time_slot, format_from_capacity
            ts_hour_map = {"УТРО": (8, 12), "ДЕНЬ": (12, 17), "ВЕЧЕР": (17, 24)}
            now = tz_now()
            # Все будущие слоты
            all_future_slots = db.query(Slot).filter(Slot.start_time >= now).order_by(Slot.start_time).all()
            # ID слотов, где клиент уже забронирован
            booked_slot_ids = {b.slot_id for b, _ in rows}

            available_slots = []
            client_bookings_list = []
            for sl in all_future_slots:
                slot_ts = slot_time_slot(sl.start_time)
                slot_fmt = format_from_capacity(sl.capacity)
                # Количество броней в слоте
                booked_count = db.query(Booking).filter(Booking.slot_id == sl.id).count()
                is_booked = sl.id in booked_slot_ids
                if is_booked:
                    client_bookings_list.append({
                        "slot_id": sl.id,
                        "start_time": sl.start_time,
                        "capacity": sl.capacity,
                        "format": slot_fmt,
                        "time_slot": slot_ts,
                        "booked": booked_count,
                    })
                    continue
                # Слот полон?
                if booked_count >= sl.capacity:
                    continue
                # Есть ли у клиента подходящий пакет?
                remaining = db.query(func.coalesce(func.sum(SubscriptionPurchase.remaining), 0)).filter(
                    SubscriptionPurchase.client_id == client_id,
                    SubscriptionPurchase.time_slot.in_([slot_ts, "-"]),
                    SubscriptionPurchase.format_name.in_([slot_fmt, "-"]),
                ).scalar() or 0
                if remaining == 0:
                    continue
                # Учитываем будущие брони клиента в том же time_slot+format
                h_start, h_end = ts_hour_map.get(slot_ts, (0, 24))
                slot_fmt_filter = case(
                    (Slot.capacity == 1, "VIP"),
                    (Slot.capacity == 2, "Double"),
                    else_="Group"
                )
                fut = db.query(Booking).join(Slot, Booking.slot_id == Slot.id).filter(
                    Booking.client_id == client_id,
                    Slot.start_time >= now,
                    func.cast(func.strftime("%H", Slot.start_time), Integer).between(h_start, h_end - 1),
                    slot_fmt_filter == slot_fmt,
                ).count()
                if fut >= remaining:
                    continue
                available_slots.append({
                    "slot_id": sl.id,
                    "start_time": sl.start_time,
                    "capacity": sl.capacity,
                    "format": slot_fmt,
                    "time_slot": slot_ts,
                    "booked": booked_count,
                    "label": f"{sl.start_time.strftime('%d.%m %H:%M')} — {slot_fmt} {slot_ts} ({booked_count}/{sl.capacity})",
                })

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
            bw = c.weight_kg or 0
            strength_data = collect_strength_data(db, client_id)
            strength_data = enrich_with_rank(strength_data, "male", bw)
            standards_table = compute_standards_table("male", bw) if bw > 0 else []

            # Будущие брони по time_slot
            from app.models import Slot as SlotModel
            future_slots = (
                db.query(SlotModel)
                .join(Booking, Booking.slot_id == SlotModel.id)
                .filter(Booking.client_id == client_id, SlotModel.start_time >= now)
                .all()
            )
            for sl in future_slots:
                ts = slot_time_slot(sl.start_time)
                booked_by_ts[ts] = booked_by_ts.get(ts, 0) + 1

            # Активные абонементы
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
                "available_slots": available_slots,
                "client_bookings": client_bookings_list,
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


@router.post("/profile/book")
def profile_book(request: Request, db: Session = Depends(get_db), slot_id: int = Form(0)):
    """Клиент бронирует слот из личного кабинета."""
    from app.models import Booking, Slot, SubscriptionPurchase
    from app.pricing import slot_time_slot, format_from_capacity
    from sqlalchemy import func, Integer, case
    from app.logging_config import audit_log

    user = get_current_user(request)
    if not user or user["role"] != "client":
        return RedirectResponse("/login", status_code=303)

    client_id = user.get("client_id")
    if not slot_id:
        return RedirectResponse("/profile", status_code=303)

    slot = db.get(Slot, slot_id)
    if not slot:
        return RedirectResponse("/profile", status_code=303)

    now = tz_now()
    if slot.start_time < now:
        return RedirectResponse("/profile", status_code=303)

    # Проверка: не забронирован ли уже
    existing = db.query(Booking).filter(Booking.slot_id == slot_id, Booking.client_id == client_id).first()
    if existing:
        return RedirectResponse("/profile", status_code=303)

    # Проверка вместимости
    booked_count = db.query(Booking).filter(Booking.slot_id == slot_id).count()
    if booked_count >= slot.capacity:
        return RedirectResponse("/profile?flash=limit_reached", status_code=303)

    # Проверка пакета
    slot_ts = slot_time_slot(slot.start_time)
    slot_fmt = format_from_capacity(slot.capacity)
    remaining = db.query(func.coalesce(func.sum(SubscriptionPurchase.remaining), 0)).filter(
        SubscriptionPurchase.client_id == client_id,
        SubscriptionPurchase.time_slot.in_([slot_ts, "-"]),
        SubscriptionPurchase.format_name.in_([slot_fmt, "-"]),
    ).scalar() or 0
    if remaining == 0:
        return RedirectResponse("/profile?flash=limit_reached", status_code=303)

    # Проверка booked_future для этого time_slot+format
    ts_hour_map = {"УТРО": (8, 12), "ДЕНЬ": (12, 17), "ВЕЧЕР": (17, 24)}
    h_start, h_end = ts_hour_map.get(slot_ts, (0, 24))
    slot_fmt_filter = case(
        (Slot.capacity == 1, "VIP"),
        (Slot.capacity == 2, "Double"),
        else_="Group"
    )
    fut = db.query(Booking).join(Slot, Booking.slot_id == Slot.id).filter(
        Booking.client_id == client_id,
        Slot.start_time >= now,
        func.cast(func.strftime("%H", Slot.start_time), Integer).between(h_start, h_end - 1),
        slot_fmt_filter == slot_fmt,
    ).count()
    if fut >= remaining:
        return RedirectResponse("/profile?flash=limit_reached", status_code=303)

    db.add(Booking(client_id=client_id, slot_id=slot_id))
    db.commit()
    audit_log("superior.audit.bookings", "ADD", client_id=client_id, slot_id=slot_id)
    return RedirectResponse("/profile", status_code=303)


@router.post("/profile/cancel")
def profile_cancel(request: Request, db: Session = Depends(get_db), slot_id: int = Form(0)):
    """Клиент отменяет свою бронь."""
    from app.models import Booking
    from app.logging_config import audit_log

    user = get_current_user(request)
    if not user or user["role"] != "client":
        return RedirectResponse("/login", status_code=303)

    if not slot_id:
        return RedirectResponse("/profile", status_code=303)

    client_id = user.get("client_id")
    db.query(Booking).filter(Booking.slot_id == slot_id, Booking.client_id == client_id).delete()
    db.commit()
    audit_log("superior.audit.bookings", "REMOVE", client_id=client_id, slot_id=slot_id)
    return RedirectResponse("/profile", status_code=303)
