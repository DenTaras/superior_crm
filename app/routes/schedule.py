"""Маршруты: календарь расписания и страница слота."""

from datetime import datetime, timedelta
from app.timezone import now as tz_now

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db, templates
from app.models import Slot, Booking, Client
from app.auth import get_current_user

router = APIRouter()


@router.get("/schedule")
def schedule(
    request: Request, db: Session = Depends(get_db),
    week_offset: int = 0, user: dict = Depends(get_current_user),
):
    """Недельный календарь 08:00–22:00."""
    slots = db.query(Slot).order_by(Slot.start_time).all()

    now = tz_now()
    base_week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_start = base_week_start + timedelta(days=7 * week_offset)
    days = [week_start + timedelta(days=i) for i in range(7)]
    hours = list(range(8, 23))

    default_time = tz_now().strftime("%Y-%m-%dT%H:%M")
    default_end_time = (tz_now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")

    grid = {(d_idx, h): None for d_idx in range(7) for h in hours}

    for slot in slots:
        if not slot.start_time:
            continue
        slot_dt = slot.start_time
        delta = slot_dt.date() - week_start.date()
        if delta.days < 0 or delta.days >= 7:
            continue
        day_index = delta.days
        hour = slot_dt.hour
        if hour in hours:
            bookings = db.query(Booking).filter(Booking.slot_id == slot.id).all()
            clients_in_slot = [db.get(Client, b.client_id) for b in bookings]
            grid[(day_index, hour)] = {
                'slot': slot,
                'booked': len(clients_in_slot),
                'clients': clients_in_slot,
            }

    return templates.TemplateResponse(
        request=request, name="schedule.html",
        context={
            "days": days, "hours": hours, "grid": grid,
            "default_time": default_time,
            "default_end_time": default_end_time,
            "week_offset": week_offset, "user": user,
        },
    )


@router.get("/slot/{slot_id}")
def slot_page(
    request: Request,
    slot_id: int,
    db: Session = Depends(get_db),
    week_offset: int = 0,
    user: dict = Depends(get_current_user),
):
    """Страница отдельного слота со списком записанных клиентов."""
    slot = db.get(Slot, slot_id)
    bookings = db.query(Booking).filter(Booking.slot_id == slot_id).all()
    clients = [db.get(Client, b.client_id) for b in bookings]
    all_clients = db.query(Client).all()

    return templates.TemplateResponse(
        request=request,
        name="slot.html",
        context={
            "slot": slot,
            "clients": clients,
            "all_clients": all_clients,
            "week_offset": week_offset,
            "user": user,
        },
    )
