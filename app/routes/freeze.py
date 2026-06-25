"""Маршруты: заморозка абонемента (защита стрика)."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db, templates
from app.models import Client, Booking, Slot, FreezeLog
from app.auth import get_current_user
from app.timezone import now as tz_now

router = APIRouter()

FREEZE_DAYS_PER_PURCHASE = 30
FREEZE_COOLDOWN_HOURS = 24


@router.post("/profile/freeze")
def profile_freeze(request: Request, db: Session = Depends(get_db)):
    """Заморозить абонемент: сохранить стрик, отменить брони."""
    user = get_current_user(request)
    if not user or user["role"] != "client":
        return RedirectResponse("/login", status_code=303)

    client_id = user.get("client_id")
    c = db.get(Client, client_id)
    if not c:
        return RedirectResponse("/profile", status_code=303)

    # Уже заморожен?
    now = tz_now()
    if c.frozen_until and c.frozen_until > now:
        return RedirectResponse("/profile?flash=Уже заморожено", status_code=303)

    # Есть ли дни заморозки?
    if c.freeze_days_remaining <= 0:
        return RedirectResponse("/profile?flash=Нет дней для заморозки", status_code=303)

    # Проверка кулдауна (24ч после разморозки)
    if c.last_freeze_cd and c.last_freeze_cd > now:
        return RedirectResponse("/profile?flash=Кулдаун 24ч после разморозки", status_code=303)

    # Отменяем все будущие бронирования
    future_bookings = (
        db.query(Booking)
        .join(Slot, Booking.slot_id == Slot.id)
        .filter(Booking.client_id == client_id, Slot.start_time >= now)
        .all()
    )
    for bk in future_bookings:
        db.delete(bk)

    # Устанавливаем заморозку на все доступные дни
    freeze_days = min(c.freeze_days_remaining, 30)
    c.frozen_until = now + timedelta(days=freeze_days)
    c.last_freeze_cd = None  # сбрасываем кулдаун (мы же заморозили)
    db.add(c)
    db.commit()

    return RedirectResponse("/profile?flash=Абонемент заморожен на " + str(freeze_days) + " дней", status_code=303)


@router.post("/profile/unfreeze")
def profile_unfreeze(request: Request, db: Session = Depends(get_db)):
    """Разморозить абонемент."""
    user = get_current_user(request)
    if not user or user["role"] != "client":
        return RedirectResponse("/login", status_code=303)

    client_id = user.get("client_id")
    c = db.get(Client, client_id)
    if not c:
        return RedirectResponse("/profile", status_code=303)

    now = tz_now()
    if not c.frozen_until or c.frozen_until <= now:
        return RedirectResponse("/profile?flash=Не заморожено", status_code=303)

    # Сколько дней реально прошло в заморозке
    frozen_days = (now - (c.frozen_until - timedelta(days=c.freeze_days_remaining))).days
    # Или проще: считаем сколько дней из заморозки было использовано
    # Создаём записи FreezeLog за каждый день заморозки
    freeze_start = c.frozen_until - timedelta(days=min(c.freeze_days_remaining, 30))
    if freeze_start < now:
        day = freeze_start
        while day < now:
            existing = db.query(FreezeLog).filter(
                FreezeLog.client_id == client_id,
                FreezeLog.date >= day,
                FreezeLog.date < day + timedelta(days=1),
            ).first()
            if not existing:
                db.add(FreezeLog(client_id=client_id, date=day, reason="freeze"))
            day += timedelta(days=1)

    # Сколько дней реально использовано
    used_days = min(c.freeze_days_remaining, max(1, (now - freeze_start).days))
    c.freeze_days_remaining = max(0, c.freeze_days_remaining - used_days)
    c.frozen_until = None
    c.last_freeze_cd = now + timedelta(hours=FREEZE_COOLDOWN_HOURS)
    db.add(c)
    db.commit()

    return RedirectResponse("/profile?flash=Абонемент разморожен. Списано " + str(used_days) + " дней", status_code=303)
