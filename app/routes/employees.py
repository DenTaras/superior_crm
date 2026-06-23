"""Маршруты: управление сотрудниками (только admin)."""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db, templates
from app.models import Employee
from app.auth import get_current_user, require_role, hash_password

router = APIRouter()


@router.get("/employees")
def employees_list(
    request: Request,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin")),
):
    """Список сотрудников."""
    employees = db.query(Employee).order_by(Employee.is_active.desc(), Employee.last_name).all()
    return templates.TemplateResponse(
        request=request, name="employees.html",
        context={"employees": employees},
    )


@router.get("/employees/create")
def employee_create_form(
    request: Request,
    _: dict = Depends(require_role("admin")),
):
    """Форма создания сотрудника."""
    return templates.TemplateResponse(
        request=request, name="employee_form.html",
        context={"employee": None, "errors": {}},
    )


@router.post("/employees/create")
def employee_create(
    request: Request,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin")),
    first_name: str = Form(...),
    last_name: str = Form(""),
    patronymic: str = Form(""),
    phone: str = Form(""),
    position: str = Form(...),
    login: str = Form(...),
    password: str = Form(""),
    salary_type: str = Form("fixed"),
    salary_amount: int = Form(0),
    regional_coefficient: int = Form(100),
    bonus_percent: int = Form(0),
    dividend_percent: int = Form(0),
):
    """Создать сотрудника."""
    errors = {}
    if not login:
        errors["login"] = "Логин обязателен"
    if db.query(Employee).filter(Employee.login == login).first():
        errors["login"] = "Логин уже занят"
    if errors:
        return templates.TemplateResponse(
            request=request, name="employee_form.html",
            context={"employee": None, "errors": errors},
        )

    emp = Employee(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        patronymic=patronymic.strip() or None,
        phone=phone.strip() or None,
        position=position,
        login=login,
        password_hash=hash_password(password) if password else None,
        salary_type=salary_type,
        salary_amount=salary_amount,
        regional_coefficient=regional_coefficient,
        bonus_percent=bonus_percent if bonus_percent else None,
        dividend_percent=dividend_percent if dividend_percent else None,
    )
    db.add(emp)
    db.commit()
    return RedirectResponse("/employees", status_code=303)


@router.get("/employees/{emp_id}/edit")
def employee_edit_form(
    request: Request,
    emp_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin")),
):
    """Форма редактирования сотрудника."""
    emp = db.get(Employee, emp_id)
    if not emp:
        return RedirectResponse("/employees", status_code=303)
    return templates.TemplateResponse(
        request=request, name="employee_form.html",
        context={"employee": emp, "errors": {}},
    )


@router.post("/employees/{emp_id}/edit")
def employee_edit(
    request: Request,
    emp_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin")),
    first_name: str = Form(...),
    last_name: str = Form(""),
    patronymic: str = Form(""),
    phone: str = Form(""),
    position: str = Form(...),
    login: str = Form(...),
    password: str = Form(""),
    salary_type: str = Form("fixed"),
    salary_amount: int = Form(0),
    regional_coefficient: int = Form(100),
    bonus_percent: int = Form(0),
    dividend_percent: int = Form(0),
):
    """Редактировать сотрудника."""
    emp = db.get(Employee, emp_id)
    if not emp:
        return RedirectResponse("/employees", status_code=303)

    errors = {}
    if not login:
        errors["login"] = "Логин обязателен"
    existing = db.query(Employee).filter(Employee.login == login, Employee.id != emp_id).first()
    if existing:
        errors["login"] = "Логин уже занят"
    if errors:
        return templates.TemplateResponse(
            request=request, name="employee_form.html",
            context={"employee": emp, "errors": errors},
        )

    emp.first_name = first_name.strip()
    emp.last_name = last_name.strip()
    emp.patronymic = patronymic.strip() or None
    emp.phone = phone.strip() or None
    emp.position = position
    emp.login = login
    if password:
        emp.password_hash = hash_password(password)
    emp.salary_type = salary_type
    emp.salary_amount = salary_amount
    emp.regional_coefficient = regional_coefficient
    emp.bonus_percent = bonus_percent if bonus_percent else None
    emp.dividend_percent = dividend_percent if dividend_percent else None
    db.commit()
    return RedirectResponse("/employees", status_code=303)


@router.post("/employees/{emp_id}/toggle")
def employee_toggle(
    emp_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin")),
):
    """Уволить / восстановить сотрудника."""
    emp = db.get(Employee, emp_id)
    if emp:
        emp.is_active = not emp.is_active
        db.commit()
    return RedirectResponse("/employees", status_code=303)
