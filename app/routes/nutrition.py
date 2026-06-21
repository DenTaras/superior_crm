"""Маршрут: питание (личный кабинет клиента)."""

import json

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db, templates
from app.models import Client, FoodRestriction, MealTemplate
from app.auth import get_current_user
from app.nutrition import generate_weekly_plan
from app.timezone import now as tz_now

router = APIRouter()


@router.get("/profile/nutrition")
def nutrition_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Страница питания: настройки + недельный план."""
    user = get_current_user(request)
    if not user or user["role"] != "client":
        return RedirectResponse("/login", status_code=303)

    client_id = user.get("client_id")
    c = db.get(Client, client_id)
    if not c:
        return RedirectResponse("/profile", status_code=303)

    # Подсчёт возраста
    age = 30
    if c.birth_year:
        age = tz_now().year - c.birth_year

    # Исключения клиента
    restrictions = db.query(FoodRestriction).filter(
        FoodRestriction.client_id == client_id
    ).all()
    excluded_tags = [r.tag for r in restrictions]

    # Генерация плана
    plan = generate_weekly_plan(
        db, client_id,
        weight_kg=c.weight_kg or 80,
        height_cm=c.height_cm or 175,
        age=age,
        sex=c.sex or "m",
        goal=c.goal or "recompose",
        activity=c.activity_level or "moderate",
        excluded_tags=excluded_tags,
    )

    # Находим индекс сегодняшнего дня
    weekday_map = {"ПН": 0, "ВТ": 1, "СР": 2, "ЧТ": 3, "ПТ": 4, "СБ": 5, "ВС": 6}
    today_idx = tz_now().weekday()
    today_name = list(weekday_map.keys())[today_idx]

    # Все доступные шаблоны для замен (с фильтром по исключениям)
    all_templates = db.query(MealTemplate).order_by(MealTemplate.sort_order).all()
    alternatives_raw = []
    for m in all_templates:
        tags = json.loads(m.tags) if m.tags else []
        if any(t in excluded_tags for t in tags):
            continue
        alternatives_raw.append({
            "id": m.id,
            "name": m.name,
            "meal_type": m.meal_type,
            "calories": m.calories,
            "protein": m.protein,
            "fat": m.fat,
            "carbs": m.carbs,
            "weight_g": m.weight_g,
            "ingredients": m.ingredients or "",
            "recipe": m.recipe or "",
            "course": m.course or "main",
        })
    alternatives_json = json.dumps(alternatives_raw, ensure_ascii=False)

    return templates.TemplateResponse(
        request=request, name="nutrition.html",
        context={
            "user": user,
            "client": c,
            "plan": plan,
            "week": plan["week"],
            "macros": plan["macros"],
            "today_name": today_name,
            "excluded_tags": excluded_tags,
            "alternatives_json": alternatives_json,
            "goal": c.goal or "recompose",
            "activity": c.activity_level or "moderate",
        },
    )


@router.post("/profile/nutrition/settings")
def nutrition_settings(
    request: Request,
    db: Session = Depends(get_db),
    goal: str = Form("recompose"),
    activity: str = Form("moderate"),
    excluded_tags: str = Form(""),
):
    """Сохранить настройки питания (цель, активность, исключения)."""
    user = get_current_user(request)
    if not user or user["role"] != "client":
        return RedirectResponse("/login", status_code=303)

    client_id = user.get("client_id")
    c = db.get(Client, client_id)
    if not c:
        return RedirectResponse("/profile", status_code=303)

    c.goal = goal
    c.activity_level = activity
    db.add(c)

    # Обновляем исключения
    db.query(FoodRestriction).filter(FoodRestriction.client_id == client_id).delete()
    if excluded_tags:
        for tag in excluded_tags.split(","):
            tag = tag.strip()
            if tag:
                db.add(FoodRestriction(client_id=client_id, tag=tag))

    db.commit()
    return RedirectResponse("/profile/nutrition", status_code=303)
