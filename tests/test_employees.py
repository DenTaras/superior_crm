"""Тесты: сотрудники, назначение тренера, бюджет."""


def test_employees_page_requires_admin(client, anon_client):
    """GET /employees — только для admin."""
    r_anon = anon_client.get("/employees", follow_redirects=False)
    assert r_anon.status_code == 303  # редирект на login

    r = client.get("/employees")
    assert r.status_code == 200
    assert "Сотрудники" in r.text


def test_employee_create(client, db_session):
    """Создание сотрудника."""
    from app.models import Employee

    r = client.post("/employees/create", data={
        "first_name": "Тест", "last_name": "Тестовый",
        "position": "trainer", "login": "test_trainer",
        "password": "pass123",
        "salary_type": "fixed",
        "salary_amount": 50000,
        "regional_coefficient": 115,
    }, follow_redirects=False)
    assert r.status_code == 303

    emp = db_session.query(Employee).filter(Employee.login == "test_trainer").first()
    assert emp is not None
    assert emp.first_name == "Тест"
    assert emp.salary_amount == 50000
    assert emp.regional_coefficient == 115


def test_employee_edit(client, db_session):
    """Редактирование сотрудника."""
    from app.models import Employee
    from app.auth import hash_password

    emp = Employee(first_name="Исх", position="trainer",
                   login="edit_emp", password_hash=hash_password("x"),
                   salary_amount=30000)
    db_session.add(emp)
    db_session.commit()

    r = client.post(f"/employees/{emp.id}/edit", data={
        "first_name": "Изменён", "last_name": "",
        "position": "trainer", "login": "edit_emp",
        "password": "", "salary_type": "fixed",
        "salary_amount": 55000, "regional_coefficient": 100,
        "bonus_percent": 0, "dividend_percent": 0,
    }, follow_redirects=False)
    assert r.status_code == 303

    db_session.refresh(emp)
    assert emp.first_name == "Изменён"
    assert emp.salary_amount == 55000


def test_employee_toggle_active(client, db_session):
    """Увольнение / восстановление сотрудника."""
    from app.models import Employee
    from app.auth import hash_password

    emp = Employee(first_name="Увол", position="trainer",
                   login="toggle_emp", password_hash=hash_password("x"))
    db_session.add(emp)
    db_session.commit()

    r = client.post(f"/employees/{emp.id}/toggle", follow_redirects=False)
    assert r.status_code == 303
    db_session.refresh(emp)
    assert emp.is_active is False

    r = client.post(f"/employees/{emp.id}/toggle", follow_redirects=False)
    assert r.status_code == 303
    db_session.refresh(emp)
    assert emp.is_active is True


def test_employee_login(anon_client, db_session):
    """Сотрудник может войти по логину/паролю."""
    from app.models import Employee
    from app.auth import hash_password

    emp = Employee(first_name="Логин", last_name="Тест",
                   position="trainer", login="log_trainer",
                   password_hash=hash_password("secret99"),
                   salary_amount=10000)
    db_session.add(emp)
    db_session.commit()

    r = anon_client.post("/login", data={"login": "log_trainer", "password": "secret99"},
                         follow_redirects=False)
    assert r.status_code == 303

    r2 = anon_client.get("/profile")
    assert r2.status_code == 200
    assert "Логин" in r2.text


def test_assign_trainer_to_slot(client, db_session):
    """Назначение тренера на слот."""
    from app.models import Slot, Employee, SlotEmployee
    from app.auth import hash_password
    from datetime import datetime

    s = Slot(start_time=datetime(2026, 7, 1, 10, 0, 0), capacity=2)
    db_session.add(s)
    db_session.flush()

    emp = Employee(first_name="Слотов", last_name="Тренер",
                   position="trainer", login="slot_trainer",
                   password_hash=hash_password("x"))
    db_session.add(emp)
    db_session.commit()

    r = client.post(f"/slot/{s.id}/assign-trainer", data={
        "employee_id": emp.id, "week_offset": 0,
    }, follow_redirects=False)
    assert r.status_code == 303

    se = db_session.query(SlotEmployee).filter(
        SlotEmployee.slot_id == s.id,
        SlotEmployee.employee_id == emp.id,
    ).first()
    assert se is not None


def test_remove_trainer_from_slot(client, db_session):
    """Удаление тренера со слота."""
    from app.models import Slot, Employee, SlotEmployee
    from app.auth import hash_password
    from datetime import datetime

    s = Slot(start_time=datetime(2026, 7, 1, 11, 0, 0), capacity=2)
    db_session.add(s)
    db_session.flush()

    emp = Employee(first_name="Удал", last_name="Тренер",
                   position="trainer", login="rem_trainer",
                   password_hash=hash_password("x"))
    db_session.add(emp)
    db_session.commit()

    db_session.add(SlotEmployee(slot_id=s.id, employee_id=emp.id))
    db_session.commit()

    r = client.post(f"/slot/{s.id}/remove-trainer", data={
        "employee_id": emp.id, "week_offset": 0,
    }, follow_redirects=False)
    assert r.status_code == 303

    se = db_session.query(SlotEmployee).filter(
        SlotEmployee.slot_id == s.id,
    ).all()
    assert len(se) == 0


def test_budget_page_shows_expenses(client):
    """Страница бюджета содержит секцию расходов."""
    from app.models import Employee
    from app.auth import hash_password
    from app.database import SessionLocal

    # Убедимся что есть сотрудники в БД (seed)
    r = client.get("/budget")
    assert r.status_code == 200
    # Должна быть секция расходов с ФОТ, УСН, чистой прибылью
    assert "ФОТ" in r.text
    assert "УСН" in r.text
    assert "Чистая прибыль" in r.text
    # Колонки взносов (МСП: 30.2% с МРОТ + 15% свыше)
    assert "Взносы 30.2%" in r.text
    assert "Взносы 15%" in r.text


def test_expense_calculation(client, db_session):
    """Проверка формул расчёта зарплаты."""
    from app.models import Employee
    from app.auth import hash_password

    emp = Employee(first_name="Расчёт", position="trainer",
                   login="calc_emp", password_hash=hash_password("x"),
                   salary_amount=40000, regional_coefficient=115,
                   bonus_percent=10)
    db_session.add(emp)
    db_session.commit()

    # Проверим страницу бюджета
    r = client.get("/budget")
    assert r.status_code == 200
    # Оклад с коэффициентом: 40000 * 1.15 = 46000
    assert "46 000" in r.text or "46000" in r.text
    # МСП: МРОТ 22440 × 1.15 = 25806; взносы 30.2% = 7793; превышение (46000-25806)=20194, 15% = 3029
    # Итого взносы = 7793 + 3029 = 10822
    assert "7 793" in r.text or "7793" in r.text
    assert "3 029" in r.text or "3029" in r.text


def test_trainer_profile_shows_slots(anon_client, db_session):
    """Профиль тренера показывает его ближайшие тренировки."""
    from app.models import Slot, Employee, SlotEmployee, Booking, Client
    from app.auth import hash_password
    from datetime import datetime, timedelta

    # Создаём слот
    s = Slot(start_time=datetime.now() + timedelta(hours=2), capacity=2)
    db_session.add(s)
    db_session.flush()

    # Создаём тренера
    emp = Employee(first_name="Профиль", last_name="Тренер",
                   position="trainer", login="prof_trainer",
                   password_hash=hash_password("prof_pass"),
                   salary_amount=30000)
    db_session.add(emp)
    db_session.commit()

    # Назначаем на слот
    db_session.add(SlotEmployee(slot_id=s.id, employee_id=emp.id))
    db_session.commit()

    # Логинимся как тренер
    anon_client.post("/login", data={"login": "prof_trainer", "password": "prof_pass"},
                     follow_redirects=False)

    r = anon_client.get("/profile")
    assert r.status_code == 200
    assert "Мои ближайшие тренировки" in r.text
