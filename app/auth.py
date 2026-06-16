"""Аутентификация и роли.

Встроенные учётные записи:
  admin / admin       — администратор (из ADMIN_LOGIN/ADMIN_PASSWORD)
  trainer / trainer   — тренер (из TRAINER_LOGIN/TRAINER_PASSWORD)
  client_1 / client_1 — клиент (логин/пароль из БД)
"""

import os
import hashlib
from typing import Optional

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db, templates
from app.models import Client

router = APIRouter()

ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
TRAINER_LOGIN = os.getenv("TRAINER_LOGIN", "trainer")
TRAINER_PASSWORD = os.getenv("TRAINER_PASSWORD", "trainer")


def hash_password(password: str) -> str:
    """Простое хеширование пароля (SHA-256 с солью)."""
    return hashlib.sha256(f"superior_salt_{password}".encode()).hexdigest()


def get_current_user(request: Request) -> Optional[dict]:
    """Вернуть информацию о текущем пользователе из сессии."""
    return request.session.get("user")


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
    # admin
    if login == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        request.session["user"] = {"role": "admin", "name": "Администратор"}
        return RedirectResponse("/", status_code=303)

    # trainer
    if login == TRAINER_LOGIN and password == TRAINER_PASSWORD:
        request.session["user"] = {"role": "trainer", "name": "Тренер"}
        return RedirectResponse("/", status_code=303)

    # client — проверка по БД
    client = db.query(Client).filter(Client.login == login).first()
    if client and client.password_hash == hash_password(password):
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
        remaining_sessions=1,  # пробное занятие
    )
    db.add(client)
    db.commit()

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
        if c:
            from app.models import Booking, Slot
            rows = (
                db.query(Booking, Slot)
                .join(Slot, Booking.slot_id == Slot.id)
                .filter(Booking.client_id == client_id)
                .order_by(Slot.start_time.desc())
                .all()
            )
            bookings = [{"slot_time": s.start_time} for b, s in rows]
        return templates.TemplateResponse(
            request=request, name="user.html",
            context={"user": user, "client": c, "bookings": bookings},
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
