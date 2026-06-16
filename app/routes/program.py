"""Маршруты: страница программы тренировки (заметки по клиентам)."""

from datetime import datetime
import json
import urllib.parse

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db, templates
from app.models import Slot, Booking, Client, TrainingNote

router = APIRouter()


@router.get("/slot/{slot_id}/program")
def slot_program(
    request: Request,
    slot_id: int,
    db: Session = Depends(get_db),
    week_offset: int = 0,
):
    """Страница программы: список клиентов + заметки."""
    slot = db.get(Slot, slot_id)
    if not slot:
        return RedirectResponse(f"/schedule?week_offset={week_offset}", status_code=303)
    bookings = db.query(Booking).filter(Booking.slot_id == slot_id).all()
    clients = [db.get(Client, b.client_id) for b in bookings]
    notes = {}
    for b in bookings:
        note = (
            db.query(TrainingNote)
            .filter(TrainingNote.slot_id == slot_id, TrainingNote.client_id == b.client_id)
            .first()
        )
        notes[str(b.client_id)] = note.text if note and note.text else ""

    return templates.TemplateResponse(
        request=request,
        name="slot_program.html",
        context={
            "slot": slot,
            "clients": clients,
            "notes_json": json.dumps(notes),
            "week_offset": week_offset,
        },
    )


@router.post("/slot/{slot_id}/program/save")
async def slot_program_save(slot_id: int, request: Request, db: Session = Depends(get_db)):
    """Сохранить заметку для клиента в слоте (form / JSON / sendBeacon)."""
    client_id = None
    text = ""
    ct = request.headers.get('content-type', '')
    try:
        if 'application/json' in ct:
            j = await request.json()
            client_id = j.get('client_id')
            text = j.get('text', '')
        elif 'application/x-www-form-urlencoded' in ct or 'multipart/form-data' in ct:
            form = await request.form()
            client_id = form.get('client_id')
            text = form.get('text', '')
        else:
            body = (await request.body()).decode(errors='ignore')
            parsed = urllib.parse.parse_qs(body)
            client_id = parsed.get('client_id', [None])[0]
            text = parsed.get('text', [''])[0]
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)

    try:
        client_id = int(client_id)
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)

    note = (
        db.query(TrainingNote)
        .filter(TrainingNote.slot_id == slot_id, TrainingNote.client_id == client_id)
        .first()
    )
    if note is None:
        note = TrainingNote(slot_id=slot_id, client_id=client_id, text=text)
    else:
        note.text = text
        note.updated_at = datetime.now()
    db.add(note)
    db.commit()
    return JSONResponse({"ok": True})
