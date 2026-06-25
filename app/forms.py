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
    login: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    height_cm: Optional[int] = Form(None),
    weight_kg: Optional[int] = Form(None),
    body_fat: Optional[int] = Form(None),
    hip_cm: Optional[int] = Form(None),
    waist_cm: Optional[int] = Form(None),
    chest_cm: Optional[int] = Form(None),
    shoulders_cm: Optional[int] = Form(None),
    biceps_cm: Optional[int] = Form(None),
    neck_cm: Optional[int] = Form(None),
    wrist_cm: Optional[int] = Form(None),
    skinfold_chest: Optional[int] = Form(None),
    skinfold_abdominal: Optional[int] = Form(None),
    skinfold_thigh: Optional[int] = Form(None),
    skinfold_triceps: Optional[int] = Form(None),
    skinfold_subscapular: Optional[int] = Form(None),
) -> ClientCreateForm:
    """Form → ClientCreateForm с валидацией."""
    return _validate(ClientCreateForm,
        first_name=first_name,
        last_name=last_name,
        patronymic=patronymic,
        birth_year=birth_year if birth_year not in (None, "") else None,
        birth_place=birth_place,
        phone=phone,
        login=login or None,
        password=password or None,
        height_cm=height_cm if height_cm not in (None, "") else None,
        weight_kg=weight_kg if weight_kg not in (None, "") else None,
        body_fat=body_fat if body_fat not in (None, "") else None,
        hip_cm=hip_cm if hip_cm not in (None, "") else None,
        waist_cm=waist_cm if waist_cm not in (None, "") else None,
        chest_cm=chest_cm if chest_cm not in (None, "") else None,
        shoulders_cm=shoulders_cm if shoulders_cm not in (None, "") else None,
        biceps_cm=biceps_cm if biceps_cm not in (None, "") else None,
        neck_cm=neck_cm if neck_cm not in (None, "") else None,
        wrist_cm=wrist_cm if wrist_cm not in (None, "") else None,
        skinfold_chest=skinfold_chest if skinfold_chest not in (None, "") else None,
        skinfold_abdominal=skinfold_abdominal if skinfold_abdominal not in (None, "") else None,
        skinfold_thigh=skinfold_thigh if skinfold_thigh not in (None, "") else None,
        skinfold_triceps=skinfold_triceps if skinfold_triceps not in (None, "") else None,
        skinfold_subscapular=skinfold_subscapular if skinfold_subscapular not in (None, "") else None,
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
    time_slot: str = Form(...),
    format_name: str = Form(...),
    package_size: int = Form(...),
) -> SubscriptionAddForm:
    """Form → SubscriptionAddForm с валидацией."""
    return _validate(SubscriptionAddForm,
        client_id=client_id, time_slot=time_slot,
        format_name=format_name, package_size=package_size,
    )
