"""Маршрут: питание v2 с нормализованными продуктами и списком покупок."""

import json

from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import RedirectResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db, templates
from app.models import Client, FoodRestriction, MealTemplate
from app.auth import get_current_user
from app.nutrition import generate_weekly_plan
from app.nutrition2 import build_shopping_list
from app.timezone import now as tz_now

router = APIRouter()


@router.get("/profile/nutrition")
def nutrition2_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Страница питания v2: план + список покупок."""
    user = get_current_user(request)
    if not user or user["role"] != "client":
        return RedirectResponse("/login", status_code=303)

    client_id = user.get("client_id")
    c = db.get(Client, client_id)
    if not c:
        return RedirectResponse("/profile", status_code=303)

    age = 30
    if c.birth_year:
        age = tz_now().year - c.birth_year

    restrictions = db.query(FoodRestriction).filter(
        FoodRestriction.client_id == client_id
    ).all()
    excluded_tags = [r.tag for r in restrictions]

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

    weekday_map = {"ПН": 0, "ВТ": 1, "СР": 2, "ЧТ": 3, "ПТ": 4, "СБ": 5, "ВС": 6}
    today_idx = tz_now().weekday()
    today_name = list(weekday_map.keys())[today_idx]

    # Все доступные шаблоны для замен
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

    # Собираем список покупок
    from app.seed_products import seed_products
    seed_products(db)
    shopping_list = build_shopping_list(plan["week"], db)

    # Группируем по категориям
    cat_labels = {
        "meat": "🥩 Мясо",
        "poultry": "🍗 Птица",
        "fish": "🐟 Рыба",
        "dairy": "🥛 Молочные продукты",
        "eggs": "🥚 Яйца",
        "vegetables": "🥦 Овощи",
        "fruit": "🍎 Фрукты",
        "berries": "🫐 Ягоды",
        "groceries": "📦 Бакалея",
        "nuts": "🥜 Орехи и семена",
        "oils": "🧴 Масло",
        "drinks": "☕ Напитки",
        "seasoning": "🧂 Специи",
        "other": "📎 Прочее",
    }
    cat_order = ["meat", "poultry", "fish", "dairy", "eggs", "vegetables",
                 "fruit", "berries", "groceries", "nuts", "oils", "drinks",
                 "seasoning", "other"]

    grouped = []
    for cat in cat_order:
        items = [item for item in shopping_list if item["category"] == cat]
        if not items:
            continue
        grouped.append({
            "label": cat_labels.get(cat, cat),
            "items": items,
        })

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
            "shopping_list": grouped,
        },
    )


@router.get("/profile/nutrition/shopping-list")
def shopping_list_export(
    request: Request,
    format: str = Query("txt"),
    db: Session = Depends(get_db),
):
    """Выгрузить список покупок в txt."""
    user = get_current_user(request)
    if not user or user["role"] != "client":
        return RedirectResponse("/login", status_code=303)

    client_id = user.get("client_id")
    c = db.get(Client, client_id)
    if not c:
        return RedirectResponse("/profile", status_code=303)

    age = 30
    if c.birth_year:
        age = tz_now().year - c.birth_year

    restrictions = db.query(FoodRestriction).filter(
        FoodRestriction.client_id == client_id
    ).all()
    excluded_tags = [r.tag for r in restrictions]

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

    shopping_list = build_shopping_list(plan["week"], db)

    cat_labels = {
        "meat": "МЯСО", "poultry": "ПТИЦА", "fish": "РЫБА",
        "dairy": "МОЛОЧНЫЕ ПРОДУКТЫ", "eggs": "ЯЙЦА",
        "vegetables": "ОВОЩИ", "fruit": "ФРУКТЫ", "berries": "ЯГОДЫ",
        "groceries": "БАКАЛЕЯ", "nuts": "ОРЕХИ И СЕМЕНА",
        "oils": "МАСЛО", "drinks": "НАПИТКИ",
        "seasoning": "СПЕЦИИ", "other": "ПРОЧЕЕ",
    }

    lines = [f"СПИСОК ПОКУПОК НА НЕДЕЛЮ", "=" * 40, ""]
    current_cat = None
    for item in shopping_list:
        if item["category"] != current_cat:
            current_cat = item["category"]
            label = cat_labels.get(current_cat, current_cat)
            lines.append(f"── {label} ──")
        lines.append(f"  {item['name']:40s} {item['display']:>10s}")

    lines.extend(["", "=" * 40, f"Всего позиций: {len(shopping_list)}"])

    return PlainTextResponse("\n".join(lines), media_type="text/plain; charset=utf-8")


@router.get("/profile/nutrition/debug")
def nutrition2_debug(
    request: Request,
    db: Session = Depends(get_db),
):
    """Отладка: показать meal_ids и MealProduct."""
    from app.seed_products import seed_products
    from app.nutrition import generate_weekly_plan, calc_bmr, calc_tdee, calc_macros
    from app.models import MealProduct as MP, Product as P, Client

    user = get_current_user(request)
    if not user:
        return PlainTextResponse("Not logged in")

    client_id = user.get("client_id")
    c = db.get(Client, client_id)
    age = 30
    if c and c.birth_year:
        age = __import__("datetime").datetime.now().year - c.birth_year

    plan = generate_weekly_plan(db, client_id or 1, 80, 175, age, "m", "recompose", "moderate")
    seed_products(db)

    lines = ["=== MEAL IDS IN PLAN ==="]
    meal_ids = set()
    for day in plan["week"]:
        for m in day["meals"]:
            mid = m.get("id")
            if mid is None:
                lines.append(f"  NO ID: {m['name']}")
            else:
                meal_ids.add(mid)
                lines.append(f"  id={mid}: {m['name']}")

    lines.append(f"\n=== MEALPRODUCT FOR THESE IDS ({len(meal_ids)} meals) ===")
    if meal_ids:
        mps = db.query(MP).filter(MP.meal_template_id.in_(list(meal_ids))).all()
        lines.append(f"  Found {len(mps)} MealProduct records")
        for mp in mps:
            p = db.query(P).filter(P.id == mp.product_id).first()
            pname = p.name if p else "???"
            lines.append(f"  meal_id={mp.meal_template_id} -> {pname} x {mp.amount}")
    else:
        lines.append("  NO MEAL IDS FOUND!")

    return PlainTextResponse("\n".join(lines), media_type="text/plain; charset=utf-8")


@router.post("/profile/nutrition/settings")
def nutrition2_settings(
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

    db.query(FoodRestriction).filter(FoodRestriction.client_id == client_id).delete()
    if excluded_tags:
        for tag in excluded_tags.split(","):
            tag = tag.strip()
            if tag:
                db.add(FoodRestriction(client_id=client_id, tag=tag))

    db.commit()

    return RedirectResponse("/profile/nutrition", status_code=303)


@router.post("/api/nutrition/macros")
def nutrition2_macros_api(
    request: Request,
    db: Session = Depends(get_db),
    goal: str = Form("recompose"),
    activity: str = Form("moderate"),
):
    """Обновить цель/активность и вернуть JSON с макросами (без перезагрузки)."""
    from app.nutrition import calc_bmr, calc_tdee, calc_macros

    user = get_current_user(request)
    if not user or user["role"] != "client":
        return {"error": "not authorized"}

    client_id = user.get("client_id")
    c = db.get(Client, client_id)
    if not c:
        return {"error": "client not found"}

    c.goal = goal
    c.activity_level = activity
    db.add(c)
    db.commit()

    age = 30
    if c.birth_year:
        age = tz_now().year - c.birth_year

    weight = c.weight_kg or 80
    height = c.height_cm or 175
    bmr = calc_bmr(weight, height, age, c.sex or "m")
    tdee = calc_tdee(bmr, activity)

    # Корректировка калорий по цели
    goal_cal_map = {"lose": -300, "gain": 300, "recompose": 0}
    target_kcal = tdee + goal_cal_map.get(goal, 0)
    macros = calc_macros(target_kcal, weight)

    return {
        "calories": macros["calories"],
        "protein": macros["protein"],
        "fat": macros["fat"],
        "carbs": macros["carbs"],
    }
