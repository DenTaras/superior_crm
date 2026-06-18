"""Тесты силовых показателей и нормативов."""

from app.strength import epley_1rm, estimate_1rm, get_rank, collect_strength_data, enrich_with_rank


def test_epley_1rm():
    """Формула Эпли: 80 кг × 10 повторений."""
    assert epley_1rm(80, 10) == round(80 * (1 + 10/30))  # ≈ 107


def test_epley_1rm_zero_reps():
    """0 повторений = 0."""
    assert epley_1rm(100, 0) == 0
    assert epley_1rm(0, 10) == 0


def test_estimate_1rm_actual():
    """1 повторение = фактический вес."""
    assert estimate_1rm(100, 1) == 100


def test_estimate_1rm_epley():
    """>1 повторение = расчёт по Эпли."""
    assert estimate_1rm(80, 10) == round(80 * (1 + 10/30))


def test_get_rank_bench():
    """Жим лёжа: 100 кг при весе 80 кг = ratio 1.25 → КМС (1.10–1.30)."""
    rank = get_rank("male", "bench", 80, 100)
    assert rank == "КМС"


def test_get_rank_deadlift():
    """Становая: 200 кг при весе 80 кг = ratio 2.5 → МСМК."""
    rank = get_rank("male", "deadlift", 80, 200)
    assert rank == "МСМК"


def test_get_rank_none():
    """Слабый результат = None (нет разряда)."""
    rank = get_rank("male", "bench", 100, 30)
    assert rank is None


def test_get_rank_zero_bodyweight():
    """Нулевой вес тела = None."""
    rank = get_rank("male", "bench", 0, 100)
    assert rank is None


def test_collect_strength_data_empty(client, db_session):
    """Для нового клиента без лога — все показатели None."""
    from app.models import Client
    c = Client(first_name="Str", last_name="Test", phone="+79990000110", remaining_sessions=0)
    db_session.add(c)
    db_session.commit()

    data = collect_strength_data(db_session, c.id)
    assert len(data) == 5
    for d in data:
        assert d["one_rm"] is None
        assert d["source"] is None


def test_collect_strength_data_with_log(anon_client, db_session):
    """Клиент с логом упражнений — 1ПМ рассчитывается."""
    from app.models import Client, Exercise, ClientExerciseLog

    c = Client(first_name="Str2", last_name="Test", phone="+79990000111", remaining_sessions=0)
    db_session.add(c)
    db_session.commit()

    # Находим упражнение "Становая тяга"
    ex = db_session.query(Exercise).filter(Exercise.name == "Становая тяга").first()
    assert ex is not None, f"Exercise 'Становая тяга' not found. Available: {[e.name for e in db_session.query(Exercise).all()]}"

    log = ClientExerciseLog(client_id=c.id, exercise_id=ex.id, weight=100, reps=5, sets=3)
    db_session.add(log)
    db_session.commit()

    data = collect_strength_data(db_session, c.id)
    deadlift_data = next(d for d in data if d["name"] == "Становая тяга")
    assert deadlift_data["one_rm"] == estimate_1rm(100, 5)  # ≈ 117
    assert deadlift_data["source"] is not None


def test_enrich_with_rank():
    """Добавление разрядов к данным."""
    data = [
        {"name": "Становая тяга", "key": "deadlift", "one_rm": 200, "source": "100×5"},
    ]
    enriched = enrich_with_rank(data, "male", 80)
    assert enriched[0]["rank"] == "МСМК"


def test_strength_data_in_profile(anon_client, db_session):
    """Силовые показатели отображаются в профиле клиента."""
    from app.models import Client, Exercise, ClientExerciseLog
    from app.auth import hash_password

    c = Client(first_name="StrengthProfile", last_name="Test", phone="+79990000112",
               login="strength_client2", password_hash=hash_password("pass"),
               remaining_sessions=5, weight_kg=80)
    db_session.add(c)
    db_session.commit()

    ex = db_session.query(Exercise).filter(Exercise.name == "Становая тяга").first()
    assert ex is not None
    log = ClientExerciseLog(client_id=c.id, exercise_id=ex.id, weight=140, reps=3, sets=3)
    db_session.add(log)
    db_session.commit()

    # Логинимся и проверяем профиль
    anon_client.post("/login", data={"login": "strength_client2", "password": "pass"}, follow_redirects=False)
    r = anon_client.get("/profile")
    assert r.status_code == 200
    assert "Силовые показатели" in r.text
    assert "Становая тяга" in r.text
    assert "140" in r.text  # вес в логе


def test_standards_table():
    """Таблица нормативов для веса 80 кг."""
    from app.strength import compute_standards_table
    table = compute_standards_table("male", 80)
    assert len(table) == 5
    deadlift_row = next(row for row in table if row["name"] == "Становая тяга")
    assert deadlift_row["МСМК"] == 200   # 2.50 × 80
    assert deadlift_row["МС"] == 176     # 2.20 × 80
    assert deadlift_row["КМС"] == 144    # 1.80 × 80


def test_standards_table_zero_weight():
    """При нулевом весе таблица пуста."""
    from app.strength import compute_standards_table
    assert compute_standards_table("male", 0) == []


def test_standards_table_in_profile(anon_client, db_session):
    """Таблица нормативов отображается в профиле."""
    from app.models import Client
    from app.auth import hash_password

    c = Client(first_name="StdProfile", last_name="Test", phone="+79990000113",
               login="std_client", password_hash=hash_password("pass"),
               remaining_sessions=5, weight_kg=80)
    db_session.add(c)
    db_session.commit()

    anon_client.post("/login", data={"login": "std_client", "password": "pass"}, follow_redirects=False)
    r = anon_client.get("/profile")
    assert r.status_code == 200
    assert "Таблица нормативов" in r.text
    assert "МСМК" in r.text
    assert "КМС" in r.text

