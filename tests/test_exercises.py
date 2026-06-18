"""Тесты API конструктора тренировок."""


def test_exercise_groups_api(client):
    """GET /api/exercise-groups возвращает список групп."""
    r = client.get("/api/exercise-groups")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0
    names = [g["name"] for g in data]
    assert "СПИНА" in names
    assert "ГРУДЬ" in names
    assert "НОГИ" in names
    assert "ПЛЕЧИ" in names


def test_exercises_api(client):
    """GET /api/exercises?group_id= возвращает упражнения группы."""
    # сначала получим ID группы СПИНА
    groups = client.get("/api/exercise-groups").json()
    back_group = next(g for g in groups if g["name"] == "СПИНА")

    r = client.get(f"/api/exercises?group_id={back_group['id']}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0
    names = [e["name"] for e in data]
    assert "Подтягивания прямым хватом" in names


def test_exercise_log_not_found(client, db_session):
    """GET /api/exercise-log для нового клиента возвращает found=false."""
    from app.models import Client
    c = Client(first_name="ExLog", last_name="Test", phone="+70000000123", remaining_sessions=0)
    db_session.add(c)
    db_session.commit()

    # берём любое упражнение
    exercises = client.get("/api/exercises?group_id=1").json()
    ex_id = exercises[0]["id"]

    r = client.get(f"/api/exercise-log?client_id={c.id}&exercise_id={ex_id}")
    assert r.status_code == 200
    assert r.json()["found"] == False


def test_exercise_log_save_and_read(client, db_session):
    """POST /api/exercise-log сохраняет, затем GET читает с прогрессией."""
    from app.models import Client
    c = Client(first_name="ExLog2", last_name="Test", phone="+70000000124", remaining_sessions=0)
    db_session.add(c)
    db_session.commit()

    exercises = client.get("/api/exercises?group_id=1").json()
    ex_id = exercises[0]["id"]

    # сохраняем
    r = client.post("/api/exercise-log", json={
        "client_id": c.id, "exercise_id": ex_id, "weight": 40, "reps": 10, "sets": 3,
    })
    assert r.status_code == 200
    assert r.json()["ok"] == True

    # читаем
    r = client.get(f"/api/exercise-log?client_id={c.id}&exercise_id={ex_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["found"] == True
    assert data["last_weight"] == 40
    assert data["last_reps"] == 10
    assert data["last_sets"] == 3
    # прогрессия 5%
    assert data["suggested_weight"] == 42  # round(40 * 1.05)
    assert data["suggested_reps"] == 10    # round(10 * 1.05) = 10 (банковское округление)
