"""Тесты модуля питания: расчёт КБЖУ, генерация плана, роуты."""

from datetime import datetime


def test_calc_bmr_male():
    """BMR мужчины: 80кг, 175см, 30 лет."""
    from app.nutrition import calc_bmr
    bmr = calc_bmr(80, 175, 30, "m")
    # 10*80 + 6.25*175 - 5*30 + 5 = 800 + 1093.75 - 150 + 5 = 1748.75
    assert bmr == 1749


def test_calc_bmr_female():
    """BMR женщины: 60кг, 165см, 25 лет."""
    from app.nutrition import calc_bmr
    bmr = calc_bmr(60, 165, 25, "f")
    # 10*60 + 6.25*165 - 5*25 - 161 = 600 + 1031.25 - 125 - 161 = 1345.25
    assert bmr == 1345


def test_calc_tdee():
    """TDEE = BMR × коэффициент."""
    from app.nutrition import calc_tdee
    assert calc_tdee(1749, "sedentary") == round(1749 * 1.2)   # 2099
    assert calc_tdee(1749, "moderate") == round(1749 * 1.55)   # 2711
    assert calc_tdee(1749, "active") == round(1749 * 1.725)    # 3017


def test_calc_macros():
    """БЖУ: белок 2г/кг, жир 25%, остаток — углеводы."""
    from app.nutrition import calc_macros
    m = calc_macros(2711, 80)
    assert m["protein"] == 160           # 80 * 2
    assert m["fat"] == round(2711 * 0.25 / 9)  # ≈ 75
    # Погрешность ±1 из-за округления
    expected_carbs = round((2711 - 160*4 - m["fat"]*9) / 4)
    assert abs(m["carbs"] - expected_carbs) <= 1


def test_generate_weekly_plan_has_7_days(client, db_session):
    """План на неделю содержит 7 дней."""
    from app.nutrition import generate_weekly_plan
    from app.seed_meals import seed_meals
    seed_meals(db_session)
    plan = generate_weekly_plan(db_session, 1, 80, 175, 30, "m", "recompose", "moderate")
    assert len(plan["week"]) == 7
    assert plan["week"][0]["day"] == "ПН"
    assert plan["week"][6]["day"] == "ВС"


def test_generate_weekly_plan_each_day_has_meals(client, db_session):
    """Каждый день содержит 6-12 приёмов (все course)."""
    from app.nutrition import generate_weekly_plan
    from app.seed_meals import seed_meals
    seed_meals(db_session)
    plan = generate_weekly_plan(db_session, 1, 80, 175, 30, "m", "recompose", "moderate")
    for d in plan["week"]:
        assert 6 <= len(d["meals"]) <= 12, f'{d["day"]}: expected 6-12 meals, got {len(d["meals"])}'


def test_generate_weekly_plan_no_duplicate_meals_in_day(client, db_session):
    """В рамках одного дня нет дубликатов блюд."""
    from app.nutrition import generate_weekly_plan
    from app.seed_meals import seed_meals
    seed_meals(db_session)
    plan = generate_weekly_plan(db_session, 1, 80, 175, 30, "m", "recompose", "moderate")
    for d in plan["week"]:
        names = [m["name"] for m in d["meals"]]
        assert len(names) == len(set(names)), f'{d["day"]}: duplicate meals: {names}'


def test_generate_weekly_plan_different_meals_each_day(client, db_session):
    """Разные дни имеют разный набор блюд (хотя бы 4 из 7 отличаются)."""
    from app.nutrition import generate_weekly_plan
    from app.seed_meals import seed_meals
    seed_meals(db_session)
    plan = generate_weekly_plan(db_session, 1, 80, 175, 30, "m", "recompose", "moderate")
    first_day = {m["name"] for m in plan["week"][0]["meals"]}
    different_days = 0
    for d in plan["week"][1:]:
        names = {m["name"] for m in d["meals"]}
        if names != first_day:
            different_days += 1
    assert different_days >= 4, f"Only {different_days} days differ from ПН"


def test_generate_weekly_plan_filters_excluded_tags(client, db_session):
    """Исключённые продукты не попадают в план."""
    from app.nutrition import generate_weekly_plan
    from app.seed_meals import seed_meals
    seed_meals(db_session)
    plan = generate_weekly_plan(db_session, 1, 80, 175, 30, "m", "recompose", "moderate",
                                 excluded_tags=["молоко"])
    for d in plan["week"]:
        for m in d["meals"]:
            # Проверяем что нет блюд с тегом молоко в названии
            assert "молок" not in m["name"].lower(), f'{m["name"]} contains dairy'


def test_generate_weekly_plan_goal_lose_reduces_calories(client, db_session):
    """Цель 'lose' даёт меньше калорий, чем 'recompose'."""
    from app.nutrition import generate_weekly_plan
    from app.seed_meals import seed_meals
    seed_meals(db_session)
    p_lose = generate_weekly_plan(db_session, 1, 80, 175, 30, "m", "lose", "moderate")
    p_maintain = generate_weekly_plan(db_session, 1, 80, 175, 30, "m", "recompose", "moderate")
    assert p_lose["target_kcal"] < p_maintain["target_kcal"]


def test_generate_weekly_plan_goal_gain_increases_calories(client, db_session):
    """Цель 'gain' даёт больше калорий, чем 'recompose'."""
    from app.nutrition import generate_weekly_plan
    from app.seed_meals import seed_meals
    seed_meals(db_session)
    p_gain = generate_weekly_plan(db_session, 1, 80, 175, 30, "m", "gain", "moderate")
    p_maintain = generate_weekly_plan(db_session, 1, 80, 175, 30, "m", "recompose", "moderate")
    assert p_gain["target_kcal"] > p_maintain["target_kcal"]


def test_nutrition_page_requires_client_role(anon_client):
    """Страница питания недоступна анониму."""
    r = anon_client.get("/profile/nutrition", follow_redirects=False)
    assert r.status_code == 303
    assert "/login" in r.headers.get("location", "")


def test_nutrition_page_shows_macros(anon_client, db_session):
    """Страница питания отображает целевые макросы."""
    from app.models import Client
    from app.auth import hash_password

    c = Client(first_name="Nutri", last_name="Test", phone="+79990000991",
               login="nutri_test", password_hash=hash_password("pass"),
               weight_kg=80, height_cm=175, birth_year=1990,
               sex="m", goal="recompose", activity_level="moderate")
    db_session.add(c)
    db_session.commit()

    anon_client.post("/login", data={"login": "nutri_test", "password": "pass"},
                     follow_redirects=False)
    r = anon_client.get("/profile/nutrition")
    assert r.status_code == 200
    assert "Цель ккал/день" in r.text
    assert "Белки (г)" in r.text
    assert "Жиры (г)" in r.text
    assert "Углеводы (г)" in r.text


def test_nutrition_page_shows_meal_table(anon_client, db_session):
    """Страница питания отображает таблицу с блюдами."""
    from app.models import Client
    from app.auth import hash_password

    c = Client(first_name="Nutri2", last_name="Test", phone="+79990000992",
               login="nutri_test2", password_hash=hash_password("pass"),
               weight_kg=80, height_cm=175, sex="m")
    db_session.add(c)
    db_session.commit()

    anon_client.post("/login", data={"login": "nutri_test2", "password": "pass"},
                     follow_redirects=False)
    r = anon_client.get("/profile/nutrition")
    assert r.status_code == 200
    assert "Завтрак" in r.text
    assert "Обед" in r.text
    assert "Ужин" in r.text
    assert "Итого" in r.text


def test_nutrition_page_day_buttons(anon_client, db_session):
    """На странице есть кнопки дней недели."""
    from app.models import Client
    from app.auth import hash_password

    c = Client(first_name="Nutri3", last_name="Test", phone="+79990000993",
               login="nutri_test3", password_hash=hash_password("pass"),
               weight_kg=80, height_cm=175, sex="m")
    db_session.add(c)
    db_session.commit()

    anon_client.post("/login", data={"login": "nutri_test3", "password": "pass"},
                     follow_redirects=False)
    r = anon_client.get("/profile/nutrition")
    assert r.status_code == 200
    for day in ("ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"):
        assert day in r.text


def test_nutrition_page_settings_form(anon_client, db_session):
    """Форма настроек отправляет и сохраняет изменения."""
    from app.models import Client, FoodRestriction
    from app.auth import hash_password

    c = Client(first_name="Nutri4", last_name="Test", phone="+79990000994",
               login="nutri_test4", password_hash=hash_password("pass"),
               weight_kg=80, height_cm=175, sex="m")
    db_session.add(c)
    db_session.commit()
    client_id = c.id

    anon_client.post("/login", data={"login": "nutri_test4", "password": "pass"},
                     follow_redirects=False)

    # Отправляем настройки
    r = anon_client.post("/profile/nutrition/settings", data={
        "goal": "lose",
        "activity": "active",
        "excluded_tags": "молоко, орехи",
    }, follow_redirects=False)
    assert r.status_code == 303

    # Проверяем что сохранилось
    c2 = db_session.get(Client, client_id)
    assert c2.goal == "lose"
    assert c2.activity_level == "active"

    restrictions = db_session.query(FoodRestriction).filter(
        FoodRestriction.client_id == client_id
    ).all()
    saved_tags = [r.tag for r in restrictions]
    assert "молоко" in saved_tags
    assert "орехи" in saved_tags


def test_nutrition_page_total_row_correct(client, db_session):
    """Итоговая строка корректно суммирует КБЖU."""
    from app.nutrition import generate_weekly_plan
    from app.seed_meals import seed_meals
    seed_meals(db_session)
    plan = generate_weekly_plan(db_session, 1, 80, 175, 30, "m", "recompose", "moderate")
    for d in plan["week"]:
        total = {"calories": 0, "protein": 0, "fat": 0, "carbs": 0, "weight_g": 0}
        for m in d["meals"]:
            for k in total:
                total[k] += m[k]
        assert d["total"]["calories"] == total["calories"], (
            f'{d["day"]}: calories {d["total"]["calories"]} vs {total["calories"]}'
        )
        assert d["total"]["protein"] == total["protein"], (
            f'{d["day"]}: protein mismatch'
        )
        assert d["total"]["fat"] == total["fat"]
        assert d["total"]["carbs"] == total["carbs"]
