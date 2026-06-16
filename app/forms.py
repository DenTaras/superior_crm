"""Зависимости FastAPI: преобразуют сырые Form-параметры в Pydantic-модели.

Использование в endpoint:
    @router.post(...)
    def create_client(form: ClientCreateForm = Depends(parse_client_form), ...):
        # form — уже провалидированный объект
"""

from typing import Optional

from fastapi import Form, Depends, HTTPException
from pydantic import ValidationError
from app.schemas import (
    ClientCreateForm,
    SlotAddForm,
    SlotEditForm,
    BookingAddForm,
    SlotRemoveForm,
    SubscriptionAddForm,
)


def _validate(model_cls, /, **kwargs):
    """Создать Pydantic-модель из kwargs, при ошибке вернуть 422."""
    try:
        return model_cls(**kwargs)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())


def parse_client_form(
    first_name: str = Form(...),
    last_name: str = Form(""),
    patronymic: str = Form(""),
    birth_year: Optional[int] = Form(None),
    birth_place: str = Form(""),
    phone: str = Form(""),
) -> ClientCreateForm:
    """Form → ClientCreateForm с валидацией."""
    return _validate(ClientCreateForm,
        first_name=first_name,
        last_name=last_name,
        patronymic=patronymic,
        birth_year=birth_year if birth_year not in (None, "") else None,
        birth_place=birth_place,
        phone=phone,
    )


def parse_slot_add_form(
    start_time: str = Form(...),
    end_time: Optional[str] = Form(None),
    capacity: int = Form(1),
    week_offset: int = Form(0),
) -> SlotAddForm:
    """Form → SlotAddForm с валидацией."""
    return _validate(SlotAddForm,
        start_time=start_time,
        end_time=end_time,
        capacity=capacity,
        week_offset=week_offset,
    )


def parse_slot_edit_form(
    start_time: str = Form(...),
    capacity: int = Form(1),
    week_offset: int = Form(0),
) -> SlotEditForm:
    """Form → SlotEditForm с валидацией."""
    return _validate(SlotEditForm,
        start_time=start_time,
        capacity=capacity,
        week_offset=week_offset,
    )


def parse_booking_add_form(
    client_id: int = Form(...),
    week_offset: int = Form(0),
) -> BookingAddForm:
    """Form → BookingAddForm с валидацией."""
    return _validate(BookingAddForm, client_id=client_id, week_offset=week_offset)


def parse_slot_remove_form(
    start_time: str = Form(None),
    end_time: str = Form(None),
    week_offset: int = Form(0),
) -> SlotRemoveForm:
    """Form → SlotRemoveForm с валидацией."""
    return _validate(SlotRemoveForm,
        start_time=start_time or "",
        end_time=end_time or "",
        week_offset=week_offset,
    )


def parse_subscription_form(
    client_id: int = Form(...),
    package: int = Form(...),
) -> SubscriptionAddForm:
    """Form → SubscriptionAddForm с валидацией."""
    return _validate(SubscriptionAddForm, client_id=client_id, package=package)
