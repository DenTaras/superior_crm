"""Маршруты: управление клиентами и абонементами."""

from datetime import datetime

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db, templates
from app.models import Client, Slot, Booking, SubscriptionPurchase
from app.schemas import ClientCreateForm, SubscriptionAddForm
from app.forms import parse_client_form, parse_subscription_form
from app.logging_config import audit_log
from app.timezone import now as tz_now
from app.auth import require_role
from app.pricing import slot_time_slot

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
        # Собираем будущие брони и группируем по time_slot
        future_bookings = (
            db.query(Slot)
            .join(Booking, Booking.slot_id == Slot.id)
            .filter(Booking.client_id == c.id, Slot.start_time >= now_dt)
            .all()
        )
        booked_by_ts: dict[str, int] = {}
        for sl in future_bookings:
            ts = slot_time_slot(sl.start_time)
            booked_by_ts[ts] = booked_by_ts.get(ts, 0) + 1
        total_booked = len(future_bookings)

        active_purchases = (
            db.query(SubscriptionPurchase)
            .filter(
                SubscriptionPurchase.client_id == c.id,
                SubscriptionPurchase.remaining > 0,
            )
            .order_by(SubscriptionPurchase.created_at.asc())
            .all()
        )
        # Группируем одинаковые (format_name, time_slot), суммируем remaining
        grouped: dict[tuple[str, str], int] = {}
        for p in active_purchases:
            key = (p.format_name, p.time_slot)
            grouped[key] = grouped.get(key, 0) + p.remaining
        purchases_list = [
            {"format_name": k[0], "time_slot": k[1], "remaining": v}
            for k, v in sorted(grouped.items())
        ]
        client_rows.append({
            "client": c,
            "active_purchases": purchases_list,
            "booked_by_time_slot": booked_by_ts,
            "total_booked": total_booked,
        })

    return templates.TemplateResponse(
        request=request, name="clients.html",
        context={
            "client_rows": client_rows, "q_name": q_name,
            "q_phone": q_phone, "page": page,
            "total_pages": total_pages, "total": total,
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

    from app.models import SubscriptionPurchase
    client = Client(
        first_name=form.first_name,
        last_name=form.last_name,
        patronymic=form.patronymic,
        birth_year=form.birth_year,
        birth_place=form.birth_place,
        phone=form.phone,
        height_cm=form.height_cm,
        weight_kg=form.weight_kg,
        body_fat=form.body_fat,
        name=f"{form.last_name} {form.first_name}".strip(),
    )
    db.add(client)
    db.flush()
    # Стартовый абонемент на 1 занятие ("Пробный")
    purchase = SubscriptionPurchase(
        client_id=client.id,
        time_slot="-",
        format_name="Пробный",
        package_size=1,
        price=0,
        remaining=1,
    )
    db.add(purchase)
    db.commit()
    audit_log("superior.audit.clients", "CREATE", client_id=client.id, phone=client.phone)
    return RedirectResponse("/clients", status_code=303)


@router.get("/clients/edit/{client_id}")
def clients_edit(
    request: Request, client_id: int, db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin", "trainer")),
):
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
        client.height_cm = form.height_cm
        client.weight_kg = form.weight_kg
        client.body_fat = form.body_fat
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
    from app.models import SubscriptionPurchase
    from app.pricing import get_price

    client = db.get(Client, form.client_id)
    if not client:
        return RedirectResponse("/clients", status_code=303)

    price = get_price(form.time_slot, form.format_name, form.package_size)
    if price is None:
        return RedirectResponse("/clients", status_code=303)

    purchase = SubscriptionPurchase(
        client_id=form.client_id,
        time_slot=form.time_slot,
        format_name=form.format_name,
        package_size=form.package_size,
        price=price,
        remaining=form.package_size,  # все занятия пока доступны
    )
    db.add(purchase)
    db.commit()
    audit_log("superior.audit.subscriptions", "ADD",
              client_id=form.client_id, package=form.package_size,
              time_slot=form.time_slot, format_name=form.format_name, price=price)
    return RedirectResponse("/clients", status_code=303)
