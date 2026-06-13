from datetime import datetime


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

    from app import Client

    created = db_session.query(Client).filter(Client.first_name == "Тест").first()
    assert created is not None

    # edit the client
    r2 = client.post(f"/clients/edit/{created.id}", data={"first_name": "Пётр", "last_name": "Клиент", "patronymic": "", "birth_year": "1990", "birth_place": "Город", "phone": "+79990000010"}, follow_redirects=False)
    assert r2.status_code == 303
    updated = db_session.get(Client, created.id)
    assert updated.first_name == "Пётр"

    # delete the client
    r3 = client.post(f"/clients/delete/{created.id}", follow_redirects=False)
    assert r3.status_code == 303
    deleted = db_session.get(Client, created.id)
    assert deleted is None
