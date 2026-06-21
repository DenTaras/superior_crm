"""Расчёт КБЖУ и генерация недельного плана питания."""

import json
import math
import random

ACTIVITY_COEFFS = {
    "sedentary": 1.2,    # сидячая работа, без тренировок
    "light": 1.375,      # 1-2 тренировки в неделю
    "moderate": 1.55,    # 3-5 тренировок
    "active": 1.725,     # 6-7 тренировок
    "extreme": 1.9,      # 2 тренировки в день / физическая работа
}

GOAL_MODIFIERS = {
    "lose": 0.80,      # -20%
    "gain": 1.15,      # +15%
    "recompose": 1.0,  # поддержание
}


def calc_bmr(weight_kg: int, height_cm: int, age: int, sex: str) -> int:
    """Mifflin-St Jeor."""
    if sex == "f":
        return round(10 * weight_kg + 6.25 * height_cm - 5 * age - 161)
    return round(10 * weight_kg + 6.25 * height_cm - 5 * age + 5)


def calc_tdee(bmr: int, activity: str) -> int:
    return round(bmr * ACTIVITY_COEFFS.get(activity, 1.2))


def calc_macros(target_kcal: int, weight_kg: int) -> dict:
    """БЖУ: белок 2г/кг, жир 25%, углеводы — остаток."""
    protein_g = round(weight_kg * 2)
    protein_kcal = protein_g * 4
    fat_kcal = round(target_kcal * 0.25)
    fat_g = round(fat_kcal / 9)
    carbs_kcal = target_kcal - protein_kcal - fat_kcal
    carbs_g = round(carbs_kcal / 4)
    return {
        "calories": target_kcal,
        "protein": protein_g,
        "fat": fat_g,
        "carbs": carbs_g,
    }


def pick_meals(pool, meal_type: str, target_kcal: int, meal_count: int = 1, rng=None, course: str = "main"):
    """Выбрать meal_count блюд из пула с суммарной калорийностью ~target_kcal."""
    if meal_type == "snack":
        # Перекусы — только из своей категории
        candidates = [m for m in pool if m["meal_type"] == "snack"]
    else:
        # Первое, второе, напиток — универсальны для завтрака/обеда/ужина
        candidates = [m for m in pool if m.get("course", "main") == course]
    if not candidates:
        return []
    if rng is None:
        rng = random
    selected = []
    remaining = target_kcal
    for _ in range(meal_count):
        if not candidates:
            break
        # Берём случайное блюдо из верхних 50% по близости к remaining
        candidates.sort(key=lambda m: abs(m["calories"] - remaining))
        top_n = max(2, len(candidates) // 2)
        if top_n > len(candidates):
            top_n = len(candidates)
        pick = candidates.pop(rng.randint(0, top_n - 1))
        selected.append(pick)
        remaining -= pick["calories"]
    return selected


def generate_weekly_plan(db, client_id: int, weight_kg: int, height_cm: int,
                          age: int, sex: str, goal: str, activity: str,
                          excluded_tags: list[str] | None = None):
    """Сгенерировать недельный план питания."""
    from app.models import MealTemplate

    excluded_tags = excluded_tags or []

    # Все шаблоны
    all_meals = db.query(MealTemplate).order_by(MealTemplate.sort_order).all()

    # Фильтруем по исключённым тегам
    pool = []
    for m in all_meals:
        tags = json.loads(m.tags) if m.tags else []
        if any(t in excluded_tags for t in tags):
            continue
        pool.append({
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

    # Расчёт КБЖУ
    bmr = calc_bmr(weight_kg, height_cm, age, sex)
    tdee = calc_tdee(bmr, activity)
    target_kcal = round(tdee * GOAL_MODIFIERS.get(goal, 1.0))
    macros = calc_macros(target_kcal, weight_kg)

    day_names = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
    week = []
    for day_idx, day_name in enumerate(day_names):
        rng = random.Random(day_idx)  # разные дни = разный выбор

        # breakfast ~25%, snack1 ~10%, lunch ~35%, snack2 ~10%, dinner ~20%
        # В lunch/breakfast/dinner может быть несколько course (first → main → drink)
        day_meals = []

        used_ids = set()

        # Сначала подбираем комби-приёмы (lunch, breakfast, dinner)
        for meal_type, course in [("breakfast", "first"), ("breakfast", "main"), ("breakfast", "drink"),
                                   ("lunch", "first"), ("lunch", "main"), ("lunch", "drink"),
                                   ("dinner", "first"), ("dinner", "main"), ("dinner", "drink")]:
            frac_map = {
                ("breakfast", "first"): 0.10,
                ("breakfast", "main"): 0.15,
                ("breakfast", "drink"): 0.02,
                ("lunch", "first"): 0.10,
                ("lunch", "main"): 0.18,
                ("lunch", "drink"): 0.02,
                ("dinner", "first"): 0.10,
                ("dinner", "main"): 0.16,
                ("dinner", "drink"): 0.02,
            }
            fraction = frac_map.get((meal_type, course), 0.10)
            if fraction <= 0:
                continue
            slot_kcal = round(target_kcal * fraction)
            available = [m for m in pool if m["id"] not in used_ids]
            picked = pick_meals(available, meal_type, slot_kcal, rng=rng, course=course)
            for m in picked:
                used_ids.add(m["id"])
                mc = dict(m)
                mc["meal_type"] = meal_type
                day_meals.append(mc)

        # Потом перекусы (snack, main)
        for _ in range(2):  # 2 перекуса
            slot_kcal = round(target_kcal * 0.10)
            available = [m for m in pool if m["id"] not in used_ids]
            picked = pick_meals(available, "snack", slot_kcal, rng=rng, course="main")
            for m in picked:
                used_ids.add(m["id"])
                day_meals.append(dict(m))

        # Масштабируем веса блюд так, чтобы итоговая калорийность дня
        # максимально совпадала с target_kcal
        actual_kcal = sum(m["calories"] for m in day_meals)
        if actual_kcal > 0 and abs(actual_kcal - target_kcal) > 10:
            scale = target_kcal / actual_kcal
            for m in day_meals:
                m["weight_g"] = max(1, round(m["weight_g"] * scale))
                m["calories"] = max(1, round(m["calories"] * scale))
                m["protein"] = max(0, round(m["protein"] * scale))
                m["fat"] = max(0, round(m["fat"] * scale))
                m["carbs"] = max(0, round(m["carbs"] * scale))

        day_total = {"calories": 0, "protein": 0, "fat": 0, "carbs": 0, "weight_g": 0}
        for m in day_meals:
            for k in day_total:
                day_total[k] += m[k]

        week.append({
            "day": day_name,
            "meals": day_meals,
            "total": day_total,
        })

    return {
        "macros": macros,
        "week": week,
        "bmr": bmr,
        "tdee": tdee,
        "target_kcal": target_kcal,
    }
