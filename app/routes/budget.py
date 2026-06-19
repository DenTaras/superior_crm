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
from app.models import SubscriptionPurchase, SubscriptionConsumption, Client
from app.auth import require_role

router = APIRouter()


@router.get("/budget")
def budget_page(
    request: Request,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin")),
):
    """Страница бюджета с финансовой статистикой и логом операций."""

    # ---- Все покупки (кроме возвращённых) ----
    purchases = (
        db.query(SubscriptionPurchase)
        .filter(SubscriptionPurchase.refunded == False)
        .order_by(SubscriptionPurchase.created_at.desc())
        .limit(100)
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

    # ---- Лог списаний (consumptions) ----
    # Показываем последние 50
    consumptions = (
        db.query(SubscriptionConsumption)
        .order_by(SubscriptionConsumption.created_at.desc())
        .limit(50)
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
        },
    )
