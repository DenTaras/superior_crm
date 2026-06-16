"""Маршруты: управление клиентами и абонементами."""

from datetime import datetime

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db, templates
from models import Client, Slot, Booking

router = APIRouter()


@router.get("/clients")
def clients_page(
    request: Request,
    db: Session = Depends(get_db),
    q_name: str = "",
    q_phone: str = "",
):
    """Список клиентов с фильтрацией по имени и телефону."""
    query = db.query(Client)
    if q_name:
        pat = f"%{q_name}%"
        query = query.filter(
            or_(
                Client.name.ilike(pat),
                Client.first_name.ilike(pat),
                Client.last_name.ilike(pat),
            )
        )
    if q_phone:
        digits = ''.join(ch for ch in q_phone if ch.isdigit())
        if digits:
            query = query.filter(
                Client.phone.ilike(f"%{digits}%") | Client.phone.ilike(f"%{q_phone}%")
            )
        else:
            query = query.filter(Client.phone.ilike(f"%{q_phone}%"))

    clients = query.order_by(Client.last_name, Client.first_name).limit(1000).all()
    now_dt = datetime.now()
    client_rows = []
    for c in clients:
        booked_future = (
            db.query(Booking)
            .join(Slot, Booking.slot_id == Slot.id)
            .filter(Booking.client_id == c.id, Slot.start_time >= now_dt)
            .count()
        )
        client_rows.append({"client": c, "booked_future": booked_future})

    return templates.TemplateResponse(
        request=request,
        name="clients.html",
        context={"client_rows": client_rows, "q_name": q_name, "q_phone": q_phone},
    )


@router.get("/clients/create")
def clients_create(request: Request):
    """Форма создания клиента."""
    return templates.TemplateResponse(request=request, name="clients_create.html", context={})


@router.post("/clients/create")
def add_client_post(
    first_name: str = Form(...),
    last_name: str = Form(""),
    patronymic: str = Form(""),
    birth_year: int = Form(None),
    birth_place: str = Form(""),
    phone: str = Form(""),
    db: Session = Depends(get_db),
):
    """Создать нового клиента."""
    first_name = (first_name or "").strip()
    if not first_name:
        return RedirectResponse("/clients", status_code=303)

    client = Client(
        first_name=first_name,
        last_name=(last_name or "").strip(),
        patronymic=(patronymic or "").strip(),
        birth_year=birth_year,
        birth_place=(birth_place or "").strip(),
        phone=(phone or "").strip(),
        name=f"{(last_name or '').strip()} {(first_name or '').strip()}".strip(),
        remaining_sessions=1,
    )
    db.add(client)
    db.commit()
    return RedirectResponse("/clients", status_code=303)


@router.get("/clients/edit/{client_id}")
def clients_edit(request: Request, client_id: int, db: Session = Depends(get_db)):
    """Форма редактирования клиента."""
    client = db.get(Client, client_id)
    if client is None:
        return RedirectResponse("/clients", status_code=303)
    return templates.TemplateResponse(
        request=request, name="clients_edit.html", context={"client": client},
    )


@router.post("/clients/edit/{client_id}")
def clients_edit_post(
    client_id: int,
    first_name: str = Form(...),
    last_name: str = Form(""),
    patronymic: str = Form(""),
    birth_year: int = Form(None),
    birth_place: str = Form(""),
    phone: str = Form(""),
    db: Session = Depends(get_db),
):
    """Обновить данные клиента."""
    client = db.get(Client, client_id)
    if client:
        client.first_name = (first_name or "").strip()
        client.last_name = (last_name or "").strip()
        client.patronymic = (patronymic or "").strip()
        client.birth_year = birth_year
        client.birth_place = (birth_place or "").strip()
        client.phone = (phone or "").strip()
        client.name = f"{client.last_name} {client.first_name}".strip()
        db.add(client)
        db.commit()
    return RedirectResponse("/clients", status_code=303)


@router.post("/clients/delete/{client_id}")
def clients_delete(client_id: int, db: Session = Depends(get_db)):
    """Удалить клиента и его бронирования."""
    db.query(Booking).filter(Booking.client_id == client_id).delete()
    db.query(Client).filter(Client.id == client_id).delete()
    db.commit()
    return RedirectResponse("/clients", status_code=303)


@router.post("/clients/add_subscription")
def clients_add_subscription(
    client_id: int = Form(...),
    package: int = Form(...),
    db: Session = Depends(get_db),
):
    """Добавить абонемент клиенту."""
    client = db.get(Client, client_id)
    try:
        package = int(package)
    except Exception:
        package = 0
    if client and package in (12, 8, 4):
        client.remaining_sessions = (client.remaining_sessions or 0) + package
        db.add(client)
        db.commit()
    return RedirectResponse("/clients", status_code=303)
