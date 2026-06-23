"""Маршруты: онлайн-оплата (создание платежа, webhook, проверка статуса)."""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db, templates
from app.models import Client, Payment, SubscriptionPurchase
from app.auth import get_current_user, require_role
from app.pricing import get_price
from app.payment import payment_provider
from app.logging_config import audit_log

_log = logging.getLogger("superior.payment")

router = APIRouter()


@router.post("/api/create-payment")
def create_payment(
    request: Request,
    time_slot: str = Form(...),
    format_name: str = Form(...),
    package_size: int = Form(...),
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("client")),
):
    """Создать платёж и вернуть ссылку на оплату (JSON)."""
    client_id = user.get("client_id")
    client = db.get(Client, client_id)
    if not client:
        return JSONResponse({"error": "Клиент не найден"}, status_code=404)

    price = get_price(time_slot, format_name, package_size)
    if price is None:
        return JSONResponse({"error": "Неверная комбинация"}, status_code=400)

    # Создаём запись о платеже
    payment = Payment(
        client_id=client_id,
        amount=price * 100,  # в копейках
        description=f"{format_name} {time_slot} {package_size}",
        metadata_json=json.dumps({
            "time_slot": time_slot,
            "format_name": format_name,
            "package_size": package_size,
        }),
    )
    db.add(payment)
    db.flush()  # получаем payment.id

    # Запрашиваем ссылку у ПШ
    try:
        redirect_url = payment_provider.create_payment(
            payment_id=str(payment.id),
            amount=payment.amount,
            description=payment.description,
            success_url=f"{request.base_url}profile?payment=success",
            cancel_url=f"{request.base_url}profile?payment=cancelled",
        )
    except Exception as e:
        _log.error("Payment creation failed: %s", e)
        db.rollback()
        return JSONResponse({"error": "Ошибка создания платежа"}, status_code=502)

    # Сохраняем provider_payment_id (если ПШ вернул его в URL, парсим)
    payment.payment_id = payment.id
    db.commit()

    return JSONResponse({"redirect_url": redirect_url})


@router.post("/api/payment-callback")
async def payment_callback(request: Request, db: Session = Depends(get_db)):
    """Webhook-обработчик от ПШ — подтверждает оплату."""
    body = await request.body()
    headers = dict(request.headers)

    try:
        data = payment_provider.verify_webhook(body, headers)
    except ValueError as e:
        _log.warning("Webhook verification failed: %s", e)
        return PlainTextResponse("invalid signature", status_code=403)

    provider_payment_id = data.get("payment_id")
    if not provider_payment_id:
        return PlainTextResponse("missing payment_id", status_code=400)

    # Ищем Payment по provider_payment_id или по внутреннему ID
    payment = db.query(Payment).filter(
        Payment.provider_payment_id == provider_payment_id
    ).first()

    # Если нет — возможно, это callback от ПШ с нашим ID в metadata
    if not payment:
        # Пробуем найти по metadata (для YooKassa)
        payment = db.query(Payment).filter(Payment.id == int(provider_payment_id)).first()

    if not payment:
        _log.warning("Payment %s not found in DB", provider_payment_id)
        return PlainTextResponse("not found", status_code=404)

    if payment.status != "pending":
        # Идемпотентность — повторный callback не обрабатываем
        return {"ok": True}

    new_status = data.get("status", "cancelled")
    if new_status == "succeeded":
        payment.status = "succeeded"
        payment.confirmed_at = datetime.now()

        # Создаём SubscriptionPurchase
        meta = json.loads(payment.metadata_json) if payment.metadata_json else {}
        purchase = SubscriptionPurchase(
            client_id=payment.client_id,
            time_slot=meta.get("time_slot", "-"),
            format_name=meta.get("format_name", "-"),
            package_size=meta.get("package_size", 1),
            price=payment.amount // 100,
            remaining=meta.get("package_size", 1),
        )
        db.add(purchase)
        db.commit()

        audit_log("superior.audit.payment", "CONFIRM",
                  payment_id=payment.id, client_id=payment.client_id,
                  amount=payment.amount, provider=payment.provider)
        _log.info("Payment %s confirmed, purchase created", payment.id)
    else:
        payment.status = new_status
        db.commit()

    return {"ok": True}


@router.get("/api/payment-status/{payment_id}")
def payment_status(
    payment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Проверить статус платежа (для JS-опроса после редиректа)."""
    payment = db.get(Payment, payment_id)
    if not payment:
        return JSONResponse({"error": "not found"}, status_code=404)

    # Клиент видит только свои платежи
    client_id = user.get("client_id")
    if client_id and payment.client_id != client_id:
        return JSONResponse({"error": "forbidden"}, status_code=403)

    return JSONResponse({
        "id": payment.id,
        "status": payment.status,
        "amount": payment.amount,
        "description": payment.description,
        "confirmed_at": payment.confirmed_at.isoformat() if payment.confirmed_at else None,
    })
