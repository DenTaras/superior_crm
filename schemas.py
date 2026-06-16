"""Pydantic схемы для документации / валидации."""

from datetime import datetime
from typing import Optional

import pydantic
from pydantic import BaseModel, Field, field_validator


class ClientSchema(BaseModel):
    id: int
    name: str
    phone: str


class SlotSchema(BaseModel):
    id: int
    start_time: datetime
    capacity: int


class BookingSchema(BaseModel):
    id: int
    client_id: int
    slot_id: int


# Совместимость Pydantic v1 / v2
try:
    pyd_major = int(pydantic.__version__.split(".")[0])
except Exception:
    pyd_major = 1

if pyd_major >= 2:
    ClientSchema.model_config = {"from_attributes": True}
    SlotSchema.model_config = {"from_attributes": True}
    BookingSchema.model_config = {"from_attributes": True}
else:
    class _Cfg:
        orm_mode = True
    ClientSchema.Config = _Cfg
    SlotSchema.Config = _Cfg
    BookingSchema.Config = _Cfg


# ---- Формы (валидация через Pydantic) ----


class ClientCreateForm(BaseModel):
    """Валидация формы создания/редактирования клиента."""
    first_name: str = Field(..., min_length=1, description="Имя (обязательно)")
    last_name: str = Field("", description="Фамилия")
    patronymic: str = Field("", description="Отчество")
    birth_year: Optional[int] = Field(None, ge=1900, le=2100, description="Год рождения")
    birth_place: str = Field("", description="Место рождения")
    phone: str = Field("", description="Телефон")

    @field_validator('first_name')
    @classmethod
    def strip_and_check(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Имя не может быть пустым')
        return v

    @field_validator('last_name', 'patronymic', 'birth_place')
    @classmethod
    def strip_optional(cls, v: str) -> str:
        return v.strip() if v else ""

    @field_validator('phone')
    @classmethod
    def clean_phone(cls, v: str) -> str:
        return v.strip() if v else ""


class SlotAddForm(BaseModel):
    """Валидация формы добавления слота(ов)."""
    start_time: str = Field(..., description="Дата и время начала (ISO)")
    end_time: Optional[str] = Field(None, description="Дата и время окончания (для массового создания)")
    capacity: int = Field(1, ge=1, le=4, description="Вместимость (1–4)")
    week_offset: int = Field(0, description="Смещение недели для редиректа")


class SlotEditForm(BaseModel):
    """Валидация формы редактирования слота."""
    start_time: str = Field(..., description="Новое время начала (ISO)")
    capacity: int = Field(1, ge=1, le=4, description="Вместимость (1–4)")
    week_offset: int = Field(0, description="Смещение недели для редиректа")


class BookingAddForm(BaseModel):
    """Валидация формы добавления бронирования."""
    client_id: int = Field(..., ge=1, description="ID клиента")
    week_offset: int = Field(0)


class SlotRemoveForm(BaseModel):
    """Валидация формы массового удаления слотов."""
    start_time: str = Field("", description="Начало интервала")
    end_time: str = Field("", description="Конец интервала")
    week_offset: int = Field(0)


class SubscriptionAddForm(BaseModel):
    """Валидация формы добавления абонемента."""
    client_id: int = Field(..., ge=1)
    package: int = Field(..., description="Пакет занятий")
