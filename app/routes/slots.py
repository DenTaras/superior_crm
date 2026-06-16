"""Маршруты: управление слотами (CRUD, массовые операции, бронирования, завершение)."""

from datetime import datetime, timedelta
import json
import time

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db, templates
from app.models import Slot, Booking, Client, JournalEntry, TrainingNote
from app.schemas import SlotAddForm, SlotEditForm, BookingAddForm, SlotRemoveForm
from app.forms import parse_slot_add_form, parse_slot_edit_form, parse_booking_add_form, parse_slot_remove_form
from app.logging_config import audit_log

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
        if start < datetime.now():
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

    now = datetime.now()
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
    audit_log("superior.audit.slots", "BULK_CREATE", count=len(candidates), start=start.isoformat(), end=end.isoformat())
    return RedirectResponse(f"/schedule?week_offset={form.week_offset}", status_code=303)


# ---- Редактирование / удаление слотов ----


@router.post("/slots/edit/{slot_id}")
def slots_edit_post(
    slot_id: int,
    form: SlotEditForm = Depends(parse_slot_edit_form),
    db: Session = Depends(get_db),
):
    """Изменить время и вместимость слота."""
    slot = db.get(Slot, slot_id)
    if slot:
        ts = form.start_time.replace(" ", "T")
        new_start = datetime.fromisoformat(ts)
        if new_start < datetime.now():
            return RedirectResponse(f"/schedule?week_offset={form.week_offset}&flash=slot_past", status_code=303)
        new_end = new_start + timedelta(hours=1)
        if _has_overlap(db, new_start, new_end, exclude_id=slot_id):
            return RedirectResponse(f"/schedule?week_offset={form.week_offset}&flash=slot_conflict", status_code=303)
        slot.start_time = new_start
        slot.capacity = _normalize_capacity(form.capacity)
        db.add(slot)
        db.commit()
        audit_log("superior.audit.slots", "UPDATE", slot_id=slot_id, time=new_start.isoformat())
    return RedirectResponse(f"/schedule?week_offset={form.week_offset}", status_code=303)


@router.post("/slots/delete/{slot_id}")
def slots_delete(slot_id: int, week_offset: int = 0, db: Session = Depends(get_db)):
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

    # проверка remaining_sessions
    now_dt = datetime.now()
    booked_future = (
        db.query(Booking)
        .join(Slot, Booking.slot_id == Slot.id)
        .filter(Booking.client_id == form.client_id, Slot.start_time >= now_dt)
        .count()
    )
    remaining = int(client.remaining_sessions or 0)
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
def complete_slot(slot_id: int, week_offset: int = 0, db: Session = Depends(get_db)):
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
            try:
                c.remaining_sessions = max(0, int(c.remaining_sessions or 0) - 1)
            except Exception:
                c.remaining_sessions = 0
            db.add(c)
            note = (
                db.query(TrainingNote)
                .filter(TrainingNote.slot_id == slot_id, TrainingNote.client_id == c.id)
                .first()
            )
            comments_map[str(c.id)] = note.text if note and note.text else ""

    entry = JournalEntry(
        slot_time=slot.start_time,
        clients=", ".join(client_names),
        comments=json.dumps(comments_map),
    )
    db.add(entry)
    db.query(Booking).filter(Booking.slot_id == slot_id).delete()
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
