from datetime import datetime

from app.models import Client


def test_clients_pagination_basic(client, db_session):
    """Пагинация: страницы работают, нет 500, навигация есть при 35+ клиентах."""
    # добавляем 35 клиентов с уникальными именами
    for i in range(35):
        db_session.add(Client(first_name=f"PgTest{i}", last_name="ZZZ",
                               phone=f"+7000000{i:04d}"))
    db_session.commit()

    # страница 1 — должна быть
    r1 = client.get("/clients?page=1")
    assert r1.status_code == 200
    assert "PgTest0" in r1.text

    # страница 2 — должна быть
    r2 = client.get("/clients?page=2")
    assert r2.status_code == 200
    assert "PgTest25" in r2.text or "PgTest" in r2.text

    # страница за пределами — не 500
    r3 = client.get("/clients?page=99")
    assert r3.status_code == 200

    # ссылка на следующую страницу
    assert "page=2" in r1.text


def test_clients_page_without_pagination_param(client):
    """Без параметра page показывается первая страница."""
    r = client.get("/clients")
    assert r.status_code == 200


def test_create_edit_delete_client(client, db_session):
    """Тест создания, редактирования и удаления клиента через HTTP-интерфейс.

    Проверяет, что клиент создаётся, затем его можно отредактировать и удалить.
    """
    # create via POST
    payload = {
        "first_name": "Тест",
        "last_name": "Клиент",
        "patronymic": "",
        "birth_year": "1990",
        "birth_place": "Город",
        "phone": "+79990000010",
    }
    r = client.post("/clients/create", data=payload, follow_redirects=False)
    assert r.status_code == 303

    from app.models import Client

    created = db_session.query(Client).filter(Client.first_name == "Тест").first()
    assert created is not None

    # edit the client
    r2 = client.post(
        f"/clients/edit/{created.id}",
        data={"first_name": "Пётр", "last_name": "Клиент", "patronymic": "",
              "birth_year": "1990", "birth_place": "Город", "phone": "+79990000010"},
        follow_redirects=False,
    )
    assert r2.status_code == 303
    updated = db_session.get(Client, created.id)
    assert updated.first_name == "Пётр"

    # delete the client
    r3 = client.post(f"/clients/delete/{created.id}", follow_redirects=False)
    assert r3.status_code == 303
    deleted = db_session.get(Client, created.id)
    assert deleted is None


def test_create_client_with_anthropometry(client, db_session):
    """Создание клиента с ростом, весом и % жира."""
    r = client.post("/clients/create", data={
        "first_name": "Антропо",
        "last_name": "Тест",
        "phone": "+79990000100",
        "height_cm": "175",
        "weight_kg": "80",
        "body_fat": "15",
    }, follow_redirects=False)
    assert r.status_code == 303

    created = db_session.query(Client).filter(Client.first_name == "Антропо").first()
    assert created is not None
    assert created.height_cm == 175
    assert created.weight_kg == 80
    assert created.body_fat == 15


def test_edit_client_anthropometry(client, db_session):
    """Редактирование роста/веса клиента."""
    from app.models import Client

    c = Client(first_name="EditAnthropo", last_name="Test", phone="+79990000101",
               height_cm=170, weight_kg=70, body_fat=20)
    db_session.add(c)
    db_session.commit()

    r = client.post(f"/clients/edit/{c.id}", data={
        "first_name": "EditAnthropo",
        "last_name": "Test",
        "phone": "+79990000101",
        "height_cm": "180",
        "weight_kg": "85",
        "body_fat": "18",
    }, follow_redirects=False)
    assert r.status_code == 303

    updated = db_session.get(Client, c.id)
    assert updated.height_cm == 180
    assert updated.weight_kg == 85
    assert updated.body_fat == 18


def test_client_anthropometry_in_profile(anon_client, db_session):
    """Антропометрия отображается в профиле клиента."""
    from app.models import Client
    from app.auth import hash_password

    c = Client(first_name="ProfileAnthropo", last_name="Test", phone="+79990000102",
               login="anthropo_client", password_hash=hash_password("pass"),
               height_cm=165, weight_kg=60, body_fat=25)
    db_session.add(c)
    db_session.commit()

    # логинимся
    anon_client.post("/login", data={"login": "anthropo_client", "password": "pass"}, follow_redirects=False)

    r = anon_client.get("/profile")
    assert r.status_code == 200
    assert "165" in r.text
    assert "60" in r.text
    assert "25" in r.text or "25%" in r.text


def test_client_profile_shows_training_history(anon_client, db_session):
    """В профиле клиента отображается история тренировок."""
    from app.models import Client, JournalEntry
    from datetime import datetime
    from app.auth import hash_password

    c = Client(first_name="HistoryClient", last_name="Test", phone="+79990000103",
               login="history_client", password_hash=hash_password("pass"))
    db_session.add(c)
    db_session.commit()

    # добавляем запись в журнал о тренировке этого клиента
    je = JournalEntry(
        created_at=datetime(2026, 6, 15, 10, 0),
        slot_time=datetime(2026, 6, 15, 10, 0),
        clients=c.fio(),  # "Test HistoryClient" — соответствует fio()
        comments='{"' + str(c.id) + '": "Подтягивания: 3×10\\nЖим: 4×8"}',
    )
    db_session.add(je)
    db_session.commit()

    # логинимся как этот клиент
    anon_client.post("/login", data={"login": "history_client", "password": "pass"}, follow_redirects=False)

    r = anon_client.get("/profile")
    assert r.status_code == 200
    assert "История тренировок" in r.text
    assert "Проведено" in r.text
    assert "Подтягивания" in r.text
    assert "Жим" in r.text
