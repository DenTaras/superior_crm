"""Нормализованная система: список покупок на основе MealProduct.

Функции:
- build_shopping_list(week, db) — собирает продукты по недельному плану
"""

from collections import defaultdict

from app.models import Product, MealProduct


def build_shopping_list(week: list[dict], db) -> list[dict]:
    """Собрать список покупок на неделю.

    Параметры:
        week — список дней, каждый с полем 'meals' (список блюд со scale-коэффициентом)
        db — сессия БД для запросов Product/MealProduct

    Возвращает:
        Список словарей:
            {"product_id": int, "name": str, "category": str, "unit": str,
             "total_amount": float, "display": str}
        Отсортирован по категории, затем по имени.
    """
    # Собираем все ID блюд из недели
    meal_ids = set()
    meal_scales = {}
    for day in week:
        for m in day["meals"]:
            mid = m.get("id")
            if mid is None:
                continue
            meal_ids.add(mid)
            base_w = m.get("_base_weight") or m.get("weight_g", 100)
            current_w = m.get("weight_g", base_w)
            scale = current_w / base_w if base_w > 0 else 1.0
            if mid not in meal_scales or scale < meal_scales[mid]:
                meal_scales[mid] = scale

    if not meal_ids:
        return []

    # Загружаем связи MealProduct
    links = (
        db.query(MealProduct, Product)
        .join(Product, MealProduct.product_id == Product.id)
        .filter(MealProduct.meal_template_id.in_(list(meal_ids)))
        .all()
    )

    # Аггрегируем
    totals = defaultdict(float)
    product_info = {}

    for mp, prod in links:
        scale = meal_scales.get(mp.meal_template_id, 1.0)
        amount = mp.amount * scale
        totals[prod.id] += amount
        product_info[prod.id] = {
            "name": prod.name,
            "category": prod.category,
            "unit": prod.unit,
        }

    # Формируем результат
    result = []
    for pid, total in sorted(totals.items(), key=lambda x: (product_info[x[0]]["category"], product_info[x[0]]["name"])):
        info = product_info[pid]
        total_rounded = round(total, 1)
        if total_rounded == int(total_rounded):
            total_rounded = int(total_rounded)
        display = f"{total_rounded} {info['unit']}"
        result.append({
            "product_id": pid,
            "name": info["name"],
            "category": info["category"],
            "unit": info["unit"],
            "total_amount": total_rounded,
            "display": display,
        })

    return result
