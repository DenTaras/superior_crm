"""Тесты nutrition2: список покупок, экспорт."""

import json


def _login_as_client(anon_client, db_session, login_suffix: str):
    """Создать клиента с role='client' и залогиниться."""
    from app.auth import hash_password
    from app.models import Client
    from app.seed_products import seed_products
    from app.seed_meals import seed_meals
    seed_meals(db_session)
    seed_products(db_session)
    login = f"nutri2_{login_suffix}"
    cl = Client(
        first_name="Тест", last_name="Питан",
        phone="+7999000099", login=login,
        password_hash=hash_password("pass"),
    )
    db_session.add(cl)
    db_session.commit()
    anon_client.post("/login", data={"login": login, "password": "pass"},
                     follow_redirects=True)
    return anon_client


def test_shopping_list_has_items(anon_client, db_session):
    """Страница nutrition2 содержит список покупок."""
    _login_as_client(anon_client, db_session, "items")
    r = anon_client.get("/profile/nutrition")
    assert r.status_code == 200
    assert "Список покупок" in r.text


def test_shopping_list_txt_export(anon_client, db_session):
    """Экспорт списка покупок в txt."""
    _login_as_client(anon_client, db_session, "txt")
    r = anon_client.get("/profile/nutrition/shopping-list?format=txt")
    assert r.status_code == 200
    assert "СПИСОК ПОКУПОК" in r.text
    assert r.headers.get("content-type", "").startswith("text/plain")


def test_build_shopping_list_empty(db_session):
    """Пустой недельный план = пустой список."""
    from app.nutrition2 import build_shopping_list
    result = build_shopping_list([], db_session)
    assert result == []


def test_seed_products_creates_records(db_session):
    """Seed создаёт продукты и связи."""
    from app.seed_meals import seed_meals
    from app.seed_products import seed_products
    from app.models import Product, MealProduct
    seed_meals(db_session)  # сначала шаблоны блюд
    seed_products(db_session)
    assert db_session.query(Product).count() > 0
    assert db_session.query(MealProduct).count() > 0


def test_product_categories_are_defined():
    """У всех продуктов есть категория."""
    from app.seed_products import PRODUCTS
    valid_cats = ("meat", "poultry", "fish", "dairy", "eggs",
                  "vegetables", "fruit", "berries", "groceries",
                  "nuts", "oils", "drinks", "seasoning", "other")
    for p in PRODUCTS:
        assert "category" in p, f"Продукт {p['name']} без категории"
        assert p["category"] in valid_cats, f"{p['name']}: неверная категория {p['category']}"


def test_every_meal_has_products(db_session):
    """У каждого MealTemplate из seed есть хотя бы один MealProduct."""
    from app.seed_meals import seed_meals
    from app.seed_products import seed_products, MEAL_PRODUCT_LINKS
    from app.seed_meals import MEAL_TEMPLATES
    seed_meals(db_session)
    seed_products(db_session)
    meal_names = {m["name"] for m in MEAL_TEMPLATES}
    linked_names = set(MEAL_PRODUCT_LINKS.keys())
    missing = meal_names - linked_names
    assert not missing, f"Блюда без продуктов: {missing}"


def test_no_duplicate_meal_names_in_db(db_session):
    """В БД нет дублирующихся имён блюд."""
    from app.seed_meals import seed_meals
    from app.models import MealTemplate
    from sqlalchemy import func
    seed_meals(db_session)
    dupes = db_session.query(MealTemplate.name, func.count(MealTemplate.id)).group_by(
        MealTemplate.name).having(func.count(MealTemplate.id) > 1).all()
    assert not dupes, f"Найдены дубликаты: {dupes}"


def test_seed_meals_cleans_duplicates(db_session):
    """seed_meals удаляет существующие дубликаты при запуске."""
    from app.models import MealTemplate
    from app.seed_meals import seed_meals
    # Создаём дубликат вручную
    original = db_session.query(MealTemplate).filter(MealTemplate.name == "Овсянка на молоке с маслом").first()
    dup = MealTemplate(name=original.name, meal_type="breakfast", course="main",
                       calories=0, protein=0, fat=0, carbs=0, weight_g=0, sort_order=999)
    db_session.add(dup)
    db_session.commit()
    assert db_session.query(MealTemplate).filter(MealTemplate.name == original.name).count() == 2

    # Запускаем seed_meals — он должен удалить дубликат
    seed_meals(db_session)
    assert db_session.query(MealTemplate).filter(MealTemplate.name == original.name).count() == 1


def test_shopping_list_covers_all_meal_products(db_session):
    """Каждый продукт из MealProduct для блюд плана попадает в итоговый список."""
    from app.seed_meals import seed_meals
    from app.seed_products import seed_products
    from app.nutrition import generate_weekly_plan
    from app.nutrition2 import build_shopping_list
    from app.models import MealProduct
    seed_meals(db_session)
    seed_products(db_session)
    plan = generate_weekly_plan(db_session, 1, 80, 175, 30, "m", "recompose", "moderate")
    lst = build_shopping_list(plan["week"], db_session)

    # Собираем все meal_id из плана
    plan_meal_ids = set()
    for day in plan["week"]:
        for m in day["meals"]:
            plan_meal_ids.add(m["id"])

    # Сколько MealProduct записей для этих meal_id
    total_mp = db_session.query(MealProduct).filter(
        MealProduct.meal_template_id.in_(list(plan_meal_ids))
    ).count()

    # В списке покупок должно быть не меньше уникальных продуктов, чем в MealProduct
    # (один продукт может использоваться в нескольких блюдах, поэтому не проверяем точное равенство)
    assert len(lst) > 0
    assert total_mp > 0
    # Каждый product_id из MealProduct представлен в итоговом списке
    lst_product_ids = {item["product_id"] for item in lst}
    mp_product_ids = set()
    for mp in db_session.query(MealProduct).filter(
            MealProduct.meal_template_id.in_(list(plan_meal_ids))
    ).all():
        mp_product_ids.add(mp.product_id)
    missing_in_list = mp_product_ids - lst_product_ids
    assert not missing_in_list, f"Продукты из MealProduct отсутствуют в списке покупок: {missing_in_list}"
