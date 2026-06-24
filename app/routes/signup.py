"""Маршрут: заявка на пробную тренировку."""

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db, templates
from app.models import TrainingRequest

router = APIRouter()


@router.get("/privacy")
def privacy_page(request: Request):
    """Политика обработки персональных данных."""
    return templates.TemplateResponse(request=request, name="privacy.html", context={})


@router.get("/gallery")
def gallery_page(request: Request):
    """Галерея студии."""
    return templates.TemplateResponse(request=request, name="gallery.html", context={})


@router.get("/signup")
def signup_page(request: Request):
    """Форма записи на пробную тренировку."""
    return templates.TemplateResponse(request=request, name="signup.html", context={})


@router.post("/signup")
def signup_post(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(""),
    phone: str = Form(""),
    goal: str = Form(""),
    preferred_time: str = Form(""),
    pd_consent: bool = Form(False),
    db: Session = Depends(get_db),
):
    """Сохранить заявку на тренировку."""
    if not pd_consent:
        return templates.TemplateResponse(
            request=request, name="signup.html",
            context={"error": "Необходимо согласие на обработку персональных данных"},
        )
    from datetime import datetime
    req = TrainingRequest(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        phone=phone.strip(),
        goal=goal.strip(),
        preferred_time=preferred_time.strip(),
        pd_consent=True,
        pd_consent_at=datetime.now(),
    )
    db.add(req)
    db.commit()
    return templates.TemplateResponse(
        request=request, name="signup_success.html",
        context={"name": f"{first_name.strip()} {last_name.strip()}".strip()},
    )
