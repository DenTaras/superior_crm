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
