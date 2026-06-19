"""Маршруты: управление слотами (CRUD, массовые операции, бронирования, завершение)."""

from datetime import datetime, timedelta
import json
import time
from app.timezone import now as tz_now

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, Integer

from app.database import get_db, templates
from app.models import Slot, Booking, Client, JournalEntry, TrainingNote, TrainingPlanExercise, ClientExerciseLog, SubscriptionPurchase, SubscriptionConsumption
from app.schemas import SlotAddForm, SlotEditForm, BookingAddForm, SlotRemoveForm
from app.forms import parse_slot_add_form, parse_slot_edit_form, parse_booking_add_form, parse_slot_remove_form
from app.logging_config import audit_log
from app.auth import require_role
from app.pricing import slot_time_slot, format_from_capacity

router = APIRouter()

_MAX_RETRIES = 3
"""Сколько раз повторить операцию при IntegrityError (race condition)."""


def _retry_on_integrity_error(fn, *args, **kwargs):
    """Выполнить fn(*args, **kwargs) с повторами при IntegrityError.

    Последний аргумент (positional) должен быть DB-сессией — в неё делаем rollback.
    """
    last_exc = None
    db = args[-1] if args else None
    for attempt in range(_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except IntegrityError as e:
            if db:
                db.rollback()
            last_exc = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(0.05 * (2 ** attempt))
    raise last_exc


# ---- Создание слотов (одиночное / массовое) ----


@router.post("/slots/add")
def slots_add(
    form: SlotAddForm = Depends(parse_slot_add_form),
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin", "trainer")),
):
    """Создать часовой слот (или серию слотов, если указан end_time).

    Вся проверка пересечений и создание — в одной транзакции.
    """
    return _retry_on_integrity_error(_do_slots_add, form, db)


def _do_slots_add(form: SlotAddForm, db: Session):
    """Внутренняя логика создания слотов (вызывается с retry)."""
    ts = (form.start_time or "").replace(" ", "T")
    try:
        start = datetime.fromisoformat(ts)
    except ValueError:
        return RedirectResponse(f"/schedule?week_offset={form.week_offset}", status_code=303)

    end = None
    if form.end_time:
        te = form.end_time.replace(" ", "T")
        try:
            end = datetime.fromisoformat(te)
        except ValueError:
            return RedirectResponse(f"/schedule?week_offset={form.week_offset}", status_code=303)

    # ---- одиночный слот ----
    if not end:
        if start < tz_now():
            return RedirectResponse(f"/schedule?week_offset={form.week_offset}&flash=slot_past", status_code=303)
        capacity = _normalize_capacity(form.capacity)
        new_end = start + timedelta(hours=1)
        if _has_overlap(db, start, new_end, exclude_id=None):
            return RedirectResponse(f"/schedule?week_offset={form.week_offset}&flash=slot_conflict", status_code=303)
        new_slot = Slot(start_time=start, capacity=capacity)
        db.add(new_slot)
        db.commit()
        audit_log("superior.audit.slots", "CREATE", slot_id=new_slot.id, time=start.isoformat())
        return RedirectResponse(f"/schedule?week_offset={form.week_offset}", status_code=303)

    # ---- массовое создание ----
    if end <= start:
        return RedirectResponse(f"/schedule?week_offset={form.week_offset}", status_code=303)

    now = tz_now()
    candidates = []
    cur = start
    while True:
        slot_end = cur + timedelta(hours=1)
        if slot_end <= end:
            if 8 <= cur.hour <= 22:
                candidates.append(cur)
        else:
            break
        cur += timedelta(hours=1)

    if any(s < now for s in candidates):
        return RedirectResponse(f"/schedule?week_offset={form.week_offset}&flash=slot_past", status_code=303)

    capacity = _normalize_capacity(form.capacity)
    for s in candidates:
        if _has_overlap(db, s, s + timedelta(hours=1), exclude_id=None):
            return RedirectResponse(f"/schedule?week_offset={form.week_offset}&flash=slot_conflict", status_code=303)

    for s in candidates:
        db.add(Slot(start_time=s, capacity=capacity))
    db.commit()
    audit_log("superior.audit.slots", "BULK_CREATE",
              count=len(candidates), start=start.isoformat(), end=end.isoformat())
    return RedirectResponse(f"/schedule?week_offset={form.week_offset}", status_code=303)


# ---- Редактирование / удаление слотов ----


@router.post("/slots/edit/{slot_id}")
def slots_edit_post(
    slot_id: int,
    form: SlotEditForm = Depends(parse_slot_edit_form),
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin", "trainer")),
):
    """Изменить время и вместимость слота."""
    slot = db.get(Slot, slot_id)
    if slot:
        ts = form.start_time.replace(" ", "T")
        new_start = datetime.fromisoformat(ts)
        if new_start < tz_now():
            return RedirectResponse(f"/schedule?week_offset={form.week_offset}&flash=slot_past", status_code=303)
        new_end = new_start + timedelta(hours=1)
        if _has_overlap(db, new_start, new_end, exclude_id=slot_id):
            return RedirectResponse(f"/schedule?week_offset={form.week_offset}&flash=slot_conflict", status_code=303)

        # Если время или вместимость изменились — очищаем брони и заметки
        time_changed = slot.start_time != new_start
        cap_changed = slot.capacity != _normalize_capacity(form.capacity)
        flash_param = ""
        if time_changed or cap_changed:
            deleted_bookings = db.query(Booking).filter(Booking.slot_id == slot_id).delete()
            db.query(TrainingNote).filter(TrainingNote.slot_id == slot_id).delete()
            if deleted_bookings > 0:
                audit_log("superior.audit.slots", "CLEAR_BOOKINGS",
                          slot_id=slot_id, count=deleted_bookings)
                flash_param = "&flash=slot_cleared"

        slot.start_time = new_start
        slot.capacity = _normalize_capacity(form.capacity)
        db.add(slot)
        db.commit()
        audit_log("superior.audit.slots", "UPDATE", slot_id=slot_id, time=new_start.isoformat())
        return RedirectResponse(f"/schedule?week_offset={form.week_offset}{flash_param}", status_code=303)
    return RedirectResponse(f"/schedule?week_offset={form.week_offset}", status_code=303)


@router.post("/slots/delete/{slot_id}")
def slots_delete(
    slot_id: int, week_offset: int = 0, db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin", "trainer")),
):
    """Удалить слот, его бронирования и заметки."""
    db.query(Booking).filter(Booking.slot_id == slot_id).delete()
    db.query(TrainingNote).filter(TrainingNote.slot_id == slot_id).delete()
    db.query(Slot).filter(Slot.id == slot_id).delete()
    db.commit()
    audit_log("superior.audit.slots", "DELETE", slot_id=slot_id)
    return RedirectResponse(f"/schedule?week_offset={week_offset}", status_code=303)


@router.post("/slots/remove")
def slots_remove(
    form: SlotRemoveForm = Depends(parse_slot_remove_form),
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin", "trainer")),
):
    """Массовое удаление слотов по интервалу."""
    if not form.start_time or not form.end_time:
        return RedirectResponse(f"/schedule?week_offset={form.week_offset}", status_code=303)
    ts = form.start_time.replace(" ", "T")
    te = form.end_time.replace(" ", "T")
    start = datetime.fromisoformat(ts)
    end = datetime.fromisoformat(te)
    if end <= start:
        return RedirectResponse(f"/schedule?week_offset={form.week_offset}", status_code=303)

    slots_to_delete = db.query(Slot).filter(Slot.start_time >= start).all()
    to_remove_ids = [s.id for s in slots_to_delete if (s.start_time + timedelta(hours=1)) <= end]
    if to_remove_ids:
        db.query(Booking).filter(Booking.slot_id.in_(to_remove_ids)).delete(synchronize_session=False)
        db.query(TrainingNote).filter(TrainingNote.slot_id.in_(to_remove_ids)).delete(synchronize_session=False)
        db.query(Slot).filter(Slot.id.in_(to_remove_ids)).delete(synchronize_session=False)
        db.commit()
    return RedirectResponse(f"/schedule?week_offset={form.week_offset}", status_code=303)


# ---- Бронирования ----


@router.post("/slot/{slot_id}/add")
def add_client(
    slot_id: int,
    form: BookingAddForm = Depends(parse_booking_add_form),
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin", "trainer")),
):
    """Записать клиента в слот (с защитой от гонок: row-level lock + retry)."""
    return _retry_on_integrity_error(_do_add_client, slot_id, form, db)


def _do_add_client(slot_id: int, form: BookingAddForm, db: Session):
    """Внутренняя логика добавления брони (вызывается с retry)."""
    # select_for_update — блокируем строку слота, чтобы два запроса
    # не прошли проверку вместимости одновременно
    slot = db.query(Slot).filter(Slot.id == slot_id).with_for_update().first()
    client = db.get(Client, form.client_id)
    week_off = form.week_offset

    if slot is None:
        return RedirectResponse(f"/schedule?week_offset={week_off}", status_code=303)
    if client is None:
        return RedirectResponse(f"/slot/{slot_id}?week_offset={week_off}&flash=limit_reached", status_code=303)

    # проверка остатка занятий по абонементам (с учётом time_slot и формата)
    now_dt = tz_now()
    slot_ts = slot_time_slot(slot.start_time)
    slot_fmt = format_from_capacity(slot.capacity)
    # Будущие брони клиента в том же time_slot и формате
    ts_hour_map = {"УТРО": (8, 12), "ДЕНЬ": (12, 17), "ВЕЧЕР": (17, 24)}
    h_start, h_end = ts_hour_map.get(slot_ts, (0, 24))
    cap = slot.capacity
    if cap <= 1:
        cap_filter = Slot.capacity <= 1
    elif cap == 2:
        cap_filter = Slot.capacity == 2
    else:
        cap_filter = Slot.capacity >= 3
    booked_future = (
        db.query(Booking)
        .join(Slot, Booking.slot_id == Slot.id)
        .filter(
            Booking.client_id == form.client_id,
            Slot.start_time >= now_dt,
            func.cast(func.strftime("%H", Slot.start_time), Integer).between(h_start, h_end - 1),
            cap_filter,
        )
        .count()
    )
    # Ищем покупки для этого time_slot, формата или универсальные (time_slot="-" / format_name="-")
    remaining = db.query(func.coalesce(func.sum(SubscriptionPurchase.remaining), 0)).filter(
        SubscriptionPurchase.client_id == form.client_id,
        SubscriptionPurchase.time_slot.in_([slot_ts, "-"]),
        SubscriptionPurchase.format_name.in_([slot_fmt, "-"]),
    ).scalar() or 0
    if remaining == 0 or booked_future >= remaining:
        return RedirectResponse(f"/slot/{slot_id}?week_offset={week_off}&flash=limit_reached", status_code=303)

    # проверка дубликата (на всякий случай — UNIQUE constraint в БД)
    existing = (
        db.query(Booking)
        .filter(Booking.slot_id == slot_id, Booking.client_id == form.client_id)
        .first()
    )
    if existing:
        return RedirectResponse(f"/slot/{slot_id}?week_offset={week_off}", status_code=303)

    # проверка вместимости (под блокировкой строки)
    count = db.query(Booking).filter(Booking.slot_id == slot_id).count()
    if count < slot.capacity:
        db.add(Booking(client_id=form.client_id, slot_id=slot_id))
        db.commit()
        audit_log("superior.audit.bookings", "ADD", client_id=form.client_id, slot_id=slot_id)
    return RedirectResponse(f"/slot/{slot_id}?week_offset={week_off}", status_code=303)


@router.post("/slot/{slot_id}/remove")
def remove_booking(
    slot_id: int,
    form: BookingAddForm = Depends(parse_booking_add_form),
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin", "trainer")),
):
    """Удалить бронь клиента из слота."""
    db.query(Booking).filter(
        Booking.slot_id == slot_id, Booking.client_id == form.client_id
    ).delete()
    db.commit()
    audit_log("superior.audit.bookings", "REMOVE", client_id=form.client_id, slot_id=slot_id)
    return RedirectResponse(f"/slot/{slot_id}?week_offset={form.week_offset}", status_code=303)


# ---- Завершение тренировки ----


@router.post("/slot/{slot_id}/complete")
def complete_slot(
    slot_id: int, week_offset: int = 0, db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin", "trainer")),
):
    """Завершить тренировку: списать занятия, сохранить в журнал, удалить слот."""
    slot = db.get(Slot, slot_id)
    if not slot:
        return RedirectResponse(f"/schedule?week_offset={week_offset}", status_code=303)

    bookings = db.query(Booking).filter(Booking.slot_id == slot_id).all()
    client_names = []
    comments_map = {}
    for b in bookings:
        c = db.get(Client, b.client_id)
        if c:
            client_names.append(c.fio())

            # Списание: ищем самый старый активный пакет для этого time_slot и формата (FIFO)
            slot_ts = slot_time_slot(slot.start_time)
            slot_fmt = format_from_capacity(slot.capacity)
            active_purchase = (
                db.query(SubscriptionPurchase)
                .filter(
                    SubscriptionPurchase.client_id == c.id,
                    SubscriptionPurchase.time_slot.in_([slot_ts, "-"]),
                    SubscriptionPurchase.format_name.in_([slot_fmt, "-"]),
                    SubscriptionPurchase.remaining > 0,
                )
                .order_by(SubscriptionPurchase.created_at.asc())
                .first()
            )
            if active_purchase:
                active_purchase.remaining -= 1
                db.add(active_purchase)
                # Логируем списание
                db.add(SubscriptionConsumption(
                    purchase_id=active_purchase.id,
                    client_id=c.id,
                    slot_id=slot_id,
                    slot_time=slot.start_time,
                ))
            note = (
                db.query(TrainingNote)
                .filter(TrainingNote.slot_id == slot_id, TrainingNote.client_id == c.id)
                .first()
            )
            comments_map[str(c.id)] = note.text if note and note.text else ""

            # Переносим фактические повторения из плана в лог упражнений
            plan_exercises = (
                db.query(TrainingPlanExercise)
                .filter(
                    TrainingPlanExercise.slot_id == slot_id,
                    TrainingPlanExercise.client_id == c.id,
                    TrainingPlanExercise.actual_reps.isnot(None),
                )
                .all()
            )
            for pe in plan_exercises:
                log_entry = ClientExerciseLog(
                    client_id=c.id,
                    exercise_id=pe.exercise_id,
                    weight=pe.weight,
                    reps=pe.actual_reps,
                    sets=pe.sets,
                )
                db.add(log_entry)

    entry = JournalEntry(
        slot_time=slot.start_time,
        clients=", ".join(client_names),
        comments=json.dumps(comments_map),
    )
    db.add(entry)
    db.query(Booking).filter(Booking.slot_id == slot_id).delete()
    db.query(TrainingPlanExercise).filter(TrainingPlanExercise.slot_id == slot_id).delete()
    db.query(TrainingNote).filter(TrainingNote.slot_id == slot_id).delete()
    db.query(Slot).filter(Slot.id == slot_id).delete()
    db.commit()
    audit_log("superior.audit.training", "COMPLETE", slot_id=slot_id, clients=", ".join(client_names))
    return RedirectResponse("/journal", status_code=303)


# ---- Вспомогательные функции ----


def _normalize_capacity(capacity: int) -> int:
    """Привести вместимость к допустимому значению {1,2,3,4}."""
    try:
        capacity = int(capacity)
    except Exception:
        return 1
    return capacity if capacity in (1, 2, 3, 4) else 1


def _has_overlap(db: Session, new_start: datetime, new_end: datetime, exclude_id: int | None) -> bool:
    """Проверить, перекрывается ли интервал с существующими слотами."""
    query = db.query(Slot).filter(
        Slot.start_time > (new_start - timedelta(hours=1)),
        Slot.start_time < new_end,
    )
    if exclude_id is not None:
        query = query.filter(Slot.id != exclude_id)
    return query.first() is not None
