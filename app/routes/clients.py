"""Маршруты: управление клиентами и абонементами."""

from datetime import datetime

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db, templates
from app.models import Client, Slot, Booking
from app.schemas import ClientCreateForm, SubscriptionAddForm
from app.forms import parse_client_form, parse_subscription_form
from app.logging_config import audit_log
from app.timezone import now as tz_now
from app.auth import require_role

router = APIRouter()


PAGE_SIZE = 25


@router.get("/clients")
def clients_page(
    request: Request,
    db: Session = Depends(get_db),
    q_name: str = "",
    q_phone: str = "",
    page: int = 1,
    _: dict = Depends(require_role("admin", "trainer")),
):
    """Список клиентов с фильтрацией и пагинацией (25 на странице)."""
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

    total = query.count()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))

    clients = (
        query.order_by(Client.last_name, Client.first_name)
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )

    now_dt = tz_now()
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
        context={
            "client_rows": client_rows,
            "q_name": q_name,
            "q_phone": q_phone,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )


@router.get("/clients/create")
def clients_create(request: Request, _: dict = Depends(require_role("admin", "trainer"))):
    """Форма создания клиента."""
    return templates.TemplateResponse(request=request, name="clients_create.html", context={})


@router.post("/clients/create")
def add_client_post(
    form: ClientCreateForm = Depends(parse_client_form),
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin", "trainer")),
):
    """Создать нового клиента."""
    if not form.first_name:
        return RedirectResponse("/clients", status_code=303)

    client = Client(
        first_name=form.first_name,
        last_name=form.last_name,
        patronymic=form.patronymic,
        birth_year=form.birth_year,
        birth_place=form.birth_place,
        phone=form.phone,
        name=f"{form.last_name} {form.first_name}".strip(),
        remaining_sessions=1,
    )
    db.add(client)
    db.commit()
    audit_log("superior.audit.clients", "CREATE", client_id=client.id, phone=client.phone)
    return RedirectResponse("/clients", status_code=303)


@router.get("/clients/edit/{client_id}")
def clients_edit(request: Request, client_id: int, db: Session = Depends(get_db), _: dict = Depends(require_role("admin", "trainer"))):
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
    form: ClientCreateForm = Depends(parse_client_form),
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin", "trainer")),
):
    """Обновить данные клиента."""
    client = db.get(Client, client_id)
    if client:
        client.first_name = form.first_name
        client.last_name = form.last_name
        client.patronymic = form.patronymic
        client.birth_year = form.birth_year
        client.birth_place = form.birth_place
        client.phone = form.phone
        client.name = f"{form.last_name} {form.first_name}".strip()
        db.add(client)
        db.commit()
        audit_log("superior.audit.clients", "UPDATE", client_id=client.id)
    return RedirectResponse("/clients", status_code=303)


@router.post("/clients/delete/{client_id}")
def clients_delete(client_id: int, db: Session = Depends(get_db), _: dict = Depends(require_role("admin", "trainer"))):
    """Удалить клиента и его бронирования."""
    db.query(Booking).filter(Booking.client_id == client_id).delete()
    db.query(Client).filter(Client.id == client_id).delete()
    db.commit()
    audit_log("superior.audit.clients", "DELETE", client_id=client_id)
    return RedirectResponse("/clients", status_code=303)


@router.post("/clients/add_subscription")
def clients_add_subscription(
    form: SubscriptionAddForm = Depends(parse_subscription_form),
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin", "trainer")),
):
    """Добавить абонемент клиенту."""
    client = db.get(Client, form.client_id)
    if client and form.package in (12, 8, 4):
        client.remaining_sessions = (client.remaining_sessions or 0) + form.package
        db.add(client)
        db.commit()
        audit_log("superior.audit.subscriptions", "ADD", client_id=form.client_id, package=form.package)
    return RedirectResponse("/clients", status_code=303)
