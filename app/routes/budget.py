"""Маршрут: бюджет и финансовая статистика (только admin).

Разделение выручки:
  - Фиксированная (earned) — за занятия, которые уже проведены.
    Возврату не подлежит.
  - Незафиксированная (unearned/deferred) — за ещё не проведённые
    занятия. Если клиент запросит возврат — уходит отсюда.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db, templates
from app.models import SubscriptionPurchase, SubscriptionConsumption, Client, Employee, Expense
from app.auth import require_role

router = APIRouter()


@router.get("/budget")
def budget_page(
    request: Request,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin")),
    year: int = 0,
    month: int = 0,
):
    """Страница бюджета с финансовой статистикой и логом операций."""
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    month_str = f"{year}-{month:02d}"

    # Начало и конец выбранного месяца
    month_start = datetime(year, month, 1)
    if month == 12:
        month_end = datetime(year + 1, 1, 1)
    else:
        month_end = datetime(year, month + 1, 1)

    # ---- Все покупки за выбранный месяц (кроме возвращённых) ----
    purchases = (
        db.query(SubscriptionPurchase)
        .filter(
            SubscriptionPurchase.refunded == False,
            SubscriptionPurchase.created_at >= month_start,
            SubscriptionPurchase.created_at < month_end,
        )
        .order_by(SubscriptionPurchase.created_at.desc())
        .all()
    )

    # ---- Расчёт выручки ----
    # На каждый купленный абонемент смотрим: сколько занятий уже провели,
    # считаем долю выручки пропорционально.
    total_earned = 0
    total_unearned = 0
    for p in purchases:
        if p.package_size > 0:
            used = p.package_size - p.remaining
            price_per = p.price / p.package_size
            total_earned += used * price_per
            total_unearned += p.remaining * price_per

    # Деньги по возвращённым абонементам
    refunded_purchases = (
        db.query(SubscriptionPurchase)
        .filter(SubscriptionPurchase.refunded == True)
        .all()
    )
    total_refunded = sum(p.price for p in refunded_purchases) if refunded_purchases else 0

    total_revenue = total_earned + total_unearned  # общая сумма всех валидных покупок
    purchases_count = len(purchases)

    month_ago = datetime.now() - timedelta(days=30)
    month_purchases = [p for p in purchases if p.created_at and p.created_at >= month_ago]
    month_revenue = sum(p.price for p in month_purchases) if month_purchases else 0

    # ---- Список покупок с именем клиента ----
    purchase_list = []
    for p in purchases:
        client = db.get(Client, p.client_id)
        name = client.fio() if client else f"#{p.client_id}"
        used = p.package_size - p.remaining
        purchase_list.append({
            "created_at": p.created_at,
            "client_name": name,
            "time_slot": p.time_slot,
            "format_name": p.format_name,
            "package_size": p.package_size,
            "price": p.price,
            "remaining": p.remaining,
            "used": used,
            "earned": round(used * (p.price / p.package_size)) if p.package_size > 0 else 0,
            "unearned": round(p.remaining * (p.price / p.package_size)) if p.package_size > 0 else 0,
        })

    # ---- Лог списаний (consumptions) за выбранный месяц ----
    consumptions = (
        db.query(SubscriptionConsumption)
        .filter(
            SubscriptionConsumption.created_at >= month_start,
            SubscriptionConsumption.created_at < month_end,
        )
        .order_by(SubscriptionConsumption.created_at.desc())
        .all()
    )
    consumption_list = []
    for cns in consumptions:
        client = db.get(Client, cns.client_id)
        name = client.fio() if client else f"#{cns.client_id}"
        purchase = db.get(SubscriptionPurchase, cns.purchase_id)
        consumption_list.append({
            "created_at": cns.created_at,
            "slot_time": cns.slot_time,
            "client_name": name,
            "format_name": purchase.format_name if purchase else "?",
            "time_slot": purchase.time_slot if purchase else "?",
        })

    return templates.TemplateResponse(
        request=request, name="budget.html",
        context={
            "total_revenue": round(total_revenue),
            "total_earned": round(total_earned),
            "total_unearned": round(total_unearned),
            "total_refunded": total_refunded,
            "purchases_count": purchases_count,
            "month_revenue": month_revenue,
            "purchases": purchase_list,
            "consumptions": consumption_list,
            "expenses": _calc_expenses(db, round(total_earned), month_str),
            "sel_year": year,
            "sel_month": month,
        },
    )


def _calc_expenses(db, monthly_revenue: int, month_str: str | None = None) -> dict:
    """Рассчитать расходы на зарплату, налоги и чистую прибыль."""
    current_month = month_str or datetime.now().strftime("%Y-%m")
    employees = db.query(Employee).filter(Employee.is_active == True).all()

    salary_total = 0
    ndfl_total = 0
    social_total = 0
    employee_details = []

    for emp in employees:
        coeff = (emp.regional_coefficient or 100) / 100.0
        salary = round(emp.salary_amount * coeff)
        ndfl = round(salary * 0.13)        # НДФЛ 13%
        social = round(salary * 0.302)     # Взносы ФОТ 30.2%
        total_cost = salary + social
        salary_total += salary
        ndfl_total += ndfl
        social_total += social

        # Премия / дивиденды
        bonus = 0
        dividend = 0
        if emp.bonus_percent:
            bonus = round(monthly_revenue * emp.bonus_percent / 100)
        if emp.dividend_percent:
            dividend = 0  # рассчитывается после вычета всех расходов

        employee_details.append({
            "name": emp.fio(),
            "position": emp.position,
            "salary": salary,
            "ndfl": ndfl,
            "social": social,
            "total_cost": total_cost,
            "take_home": salary - ndfl,
            "bonus": bonus,
        })

    # Расходы из БД (аренда, прочее)
    manual_expenses = db.query(Expense).filter(Expense.month == current_month).all()
    rent_total = sum(e.amount for e in manual_expenses if e.category == "rent")
    other_total = sum(e.amount for e in manual_expenses if e.category == "other")

    fot_total = salary_total + social_total
    usn_tax = round(monthly_revenue * 0.06)  # УСН 6%
    total_expenses = fot_total + usn_tax + rent_total + other_total

    # Дивиденды (после всех расходов)
    net_profit_before_dividends = monthly_revenue - total_expenses
    dividend_total = 0
    for emp in employees:
        if emp.dividend_percent:
            dividend_total += round(net_profit_before_dividends * emp.dividend_percent / 100)

    net_profit = net_profit_before_dividends - dividend_total

    return {
        "employees": employee_details,
        "salary_total": salary_total,
        "ndfl_total": ndfl_total,
        "social_total": social_total,
        "fot_total": fot_total,
        "usn_tax": usn_tax,
        "rent_total": rent_total,
        "other_total": other_total,
        "total_expenses": total_expenses,
        "dividend_total": dividend_total,
        "net_profit": net_profit,
    }
