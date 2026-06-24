"""Маршруты: журнал проведённых занятий и информация."""

import json

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db, templates
from app.models import JournalEntry, Client
from app.auth import require_role

router = APIRouter()


@router.get("/")
def home(request: Request):
    """Главная информационная страница."""
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})


@router.get("/journal")
def journal_page(request: Request, db: Session = Depends(get_db), _: dict = Depends(require_role("admin", "trainer"))):
    """Журнал проведённых занятий."""
    raw = db.query(JournalEntry).order_by(JournalEntry.created_at.desc()).all()
    entries = []
    for e in raw:
        comments_map = {}
        try:
            if e.comments:
                comments_map = json.loads(e.comments)
        except Exception as ex:
            import logging as _lg
            _lg.getLogger("superior.request").warning("JOURNAL: failed to parse comments: %s", ex)
            comments_map = {}
        comments_list = []
        for cid, text in comments_map.items():
            try:
                c = db.get(Client, int(cid))
                name = c.fio() if c else f"#{cid}"
            except Exception as ex:
                _lg.getLogger("superior.request").warning("JOURNAL: failed to resolve client %s: %s", cid, ex)
                name = f"#{cid}"
            comments_list.append((name, text))
        entries.append({"entry": e, "comments": comments_list})
    return templates.TemplateResponse(
        request=request, name="journal.html", context={"entries": entries},
    )


@router.get("/subscriptions")
def subscriptions_page(request: Request):
    """Публичная страница с информацией об абонементах и ценах."""
    from app.pricing import PRICING, TIME_SLOTS, FORMATS, PACKAGE_SIZES

    # Находим самую выгодную цену за занятие
    best_price_per_session = float("inf")
    best_key = None
    for ts in TIME_SLOTS:
        for fmt in FORMATS:
            for size in PACKAGE_SIZES:
                price = PRICING[ts][fmt][size]
                per_session = price / size
                if per_session < best_price_per_session:
                    best_price_per_session = per_session
                    best_key = (ts, fmt, size)
                elif per_session == best_price_per_session and size > (best_key[2] if best_key else 0):
                    best_key = (ts, fmt, size)

    return templates.TemplateResponse(
        request=request, name="subscriptions.html",
        context={
            "pricing": PRICING,
            "time_slots": TIME_SLOTS,
            "formats": FORMATS,
            "package_sizes": PACKAGE_SIZES,
            "best_deal": best_key,
        },
    )


@router.get("/contacts")
def contacts_page(request: Request):
    """Публичная страница с контактами студии."""
    return templates.TemplateResponse(request=request, name="contacts.html", context={})
