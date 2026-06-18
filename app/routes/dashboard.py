"""Маршрут: дашборд с аналитикой и графиками (admin/trainer)."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.database import get_db, templates
from app.models import SubscriptionPurchase, Client, Slot, Booking, JournalEntry
from app.auth import require_role

router = APIRouter()


@router.get("/dashboard")
def dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
    agg: str = "month",
    _: dict = Depends(require_role("admin", "trainer")),
):
    """Дашборд с финансовой статистикой и активностями.

    Параметр agg: month (по умолчанию), day, hour.
    """
    now = datetime.now()

    # --- Определяем период и шаг агрегации ---
    if agg == "hour":
        since = now - timedelta(days=7)
        date_parts = [
            extract("year", SubscriptionPurchase.created_at).label("year"),
            extract("month", SubscriptionPurchase.created_at).label("month"),
            extract("day", SubscriptionPurchase.created_at).label("day"),
            extract("hour", SubscriptionPurchase.created_at).label("hour"),
        ]
        group_cols = ["year", "month", "day", "hour"]
        order_cols = ["year", "month", "day", "hour"]
        fmt_label = lambda r: f"{int(r.day):02d}.{int(r.month):02d} {int(r.hour):02d}:00"
    elif agg == "day":
        since = now - timedelta(days=90)
        date_parts = [
            extract("year", SubscriptionPurchase.created_at).label("year"),
            extract("month", SubscriptionPurchase.created_at).label("month"),
            extract("day", SubscriptionPurchase.created_at).label("day"),
        ]
        group_cols = ["year", "month", "day"]
        order_cols = ["year", "month", "day"]
        fmt_label = lambda r: f"{int(r.day):02d}.{int(r.month):02d}"
    else:  # month
        since = now - timedelta(days=365)
        date_parts = [
            extract("year", SubscriptionPurchase.created_at).label("year"),
            extract("month", SubscriptionPurchase.created_at).label("month"),
        ]
        group_cols = ["year", "month"]
        order_cols = ["year", "month"]
        fmt_label = lambda r: f"{int(r.year)}-{int(r.month):02d}"

    # --- Выручка по времени ---
    rows = (
        db.query(*date_parts, func.sum(SubscriptionPurchase.price).label("total"))
        .filter(SubscriptionPurchase.created_at >= since)
        .group_by(*group_cols)
        .order_by(*order_cols)
        .all()
    )
    labels = []
    revenues = []
    for r in rows:
        labels.append(fmt_label(r))
        revenues.append(int(r.total))

    # --- Выручка по временным слотам ---
    slot_revenue = (
        db.query(
            SubscriptionPurchase.time_slot,
            func.sum(SubscriptionPurchase.price).label("total"),
        )
        .filter(SubscriptionPurchase.created_at >= since)
        .group_by(SubscriptionPurchase.time_slot)
        .all()
    )
    slot_labels = [r.time_slot for r in slot_revenue]
    slot_data = [int(r.total) for r in slot_revenue]

    # --- Выручка по форматам ---
    fmt_revenue = (
        db.query(
            SubscriptionPurchase.format_name,
            func.sum(SubscriptionPurchase.price).label("total"),
        )
        .filter(SubscriptionPurchase.created_at >= since)
        .group_by(SubscriptionPurchase.format_name)
        .all()
    )
    fmt_labels_list = [r.format_name for r in fmt_revenue]
    fmt_data = [int(r.total) for r in fmt_revenue]

    # --- Активные клиенты ---
    active_clients = (
        db.query(SubscriptionPurchase.client_id)
        .filter(SubscriptionPurchase.remaining > 0)
        .distinct()
        .count()
    )
    total_clients = db.query(Client).count()
    month_ago = now - timedelta(days=30)
    month_trainings = (
        db.query(JournalEntry)
        .filter(JournalEntry.created_at >= month_ago)
        .count()
    )

    # --- Последние продажи ---
    recent_purchases = (
        db.query(SubscriptionPurchase)
        .order_by(SubscriptionPurchase.created_at.desc())
        .limit(10)
        .all()
    )
    recent_list = []
    for p in recent_purchases:
        cl = db.get(Client, p.client_id)
        recent_list.append({
            "date": p.created_at,
            "client_name": cl.fio() if cl else f"#{p.client_id}",
            "label": f"{p.format_name} {p.time_slot} {p.package_size}",
            "price": p.price,
        })

    # --- Название оси X ---
    axis_label = {"hour": "Час", "day": "День", "month": "Месяц"}.get(agg, "Месяц")

    return templates.TemplateResponse(
        request=request, name="dashboard.html",
        context={
            "labels": labels,
            "revenues": revenues,
            "slot_labels": slot_labels,
            "slot_data": slot_data,
            "fmt_labels": fmt_labels_list,
            "fmt_data": fmt_data,
            "active_clients": active_clients,
            "total_clients": total_clients,
            "month_trainings": month_trainings,
            "recent_purchases": recent_list,
            "current_agg": agg,
            "axis_label": axis_label,
        },
    )
