"""Маршрут: бюджет и финансовая статистика (только admin)."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from app.database import get_db, templates
from app.models import SubscriptionPurchase, Client
from app.auth import require_role

router = APIRouter()


@router.get("/budget")
def budget_page(
    request: Request,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin")),
):
    """Страница бюджета с финансовой статистикой."""
    purchases = (
        db.query(SubscriptionPurchase)
        .order_by(SubscriptionPurchase.created_at.desc())
        .limit(100)
        .all()
    )

    total_revenue = sum(p.price for p in purchases) if purchases else 0
    purchases_count = len(purchases)

    month_ago = datetime.now() - timedelta(days=30)
    month_purchases = [p for p in purchases if p.created_at and p.created_at >= month_ago]
    month_revenue = sum(p.price for p in month_purchases) if month_purchases else 0

    purchase_list = []
    for p in purchases:
        client = db.get(Client, p.client_id)
        purchase_list.append({
            "created_at": p.created_at,
            "client_name": client.fio() if client else f"#{p.client_id}",
            "time_slot": p.time_slot,
            "format_name": p.format_name,
            "package_size": p.package_size,
            "price": p.price,
        })

    return templates.TemplateResponse(
        request=request, name="budget.html",
        context={
            "total_revenue": total_revenue,
            "purchases_count": purchases_count,
            "month_revenue": month_revenue,
            "purchases": purchase_list,
        },
    )
