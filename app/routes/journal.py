"""Маршруты: журнал проведённых занятий и информация."""

import json

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db, templates
from app.models import JournalEntry, Client

router = APIRouter()


@router.get("/")
def home(request: Request):
    """Главная информационная страница."""
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})


@router.get("/journal")
def journal_page(request: Request, db: Session = Depends(get_db)):
    """Журнал проведённых занятий."""
    raw = db.query(JournalEntry).order_by(JournalEntry.created_at.desc()).all()
    entries = []
    for e in raw:
        comments_map = {}
        try:
            if e.comments:
                comments_map = json.loads(e.comments)
        except Exception:
            comments_map = {}
        comments_list = []
        for cid, text in comments_map.items():
            try:
                c = db.get(Client, int(cid))
                name = c.fio() if c else f"#{cid}"
            except Exception:
                name = f"#{cid}"
            comments_list.append((name, text))
        entries.append({"entry": e, "comments": comments_list})
    return templates.TemplateResponse(
        request=request, name="journal.html", context={"entries": entries},
    )


@router.get("/subscriptions")
def subscriptions_page(request: Request):
    """Страница с перечнем абонементов."""
    return templates.TemplateResponse(request=request, name="subscriptions.html", context={})
