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
except Exception as ex:
    print(f"[WARN] Failed to detect pydantic version: {ex}, assuming v1")
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
    login: Optional[str] = Field(None, description="Логин для входа")
    password: Optional[str] = Field(None, description="Пароль (оставьте пустым, чтобы не менять)")
    height_cm: Optional[int] = Field(None, ge=50, le=250, description="Рост (см)")
    weight_kg: Optional[int] = Field(None, ge=20, le=300, description="Вес (кг)")
    body_fat: Optional[int] = Field(None, ge=0, le=99, description="% жира")
    hip_cm: Optional[int] = Field(None, ge=0, le=200, description="Бедро (см)")
    waist_cm: Optional[int] = Field(None, ge=0, le=200, description="Талия (см)")
    chest_cm: Optional[int] = Field(None, ge=0, le=200, description="Грудь (см)")
    shoulders_cm: Optional[int] = Field(None, ge=0, le=200, description="Плечи (см)")
    biceps_cm: Optional[int] = Field(None, ge=0, le=100, description="Бицепс (см)")
    neck_cm: Optional[int] = Field(None, ge=0, le=100, description="Шея (см)")
    wrist_cm: Optional[int] = Field(None, ge=0, le=50, description="Запястье (см)")
    skinfold_chest: Optional[int] = Field(None, ge=0, le=100, description="Кож.складка грудь (мм)")
    skinfold_abdominal: Optional[int] = Field(None, ge=0, le=100, description="Кож.складка живот (мм)")
    skinfold_thigh: Optional[int] = Field(None, ge=0, le=100, description="Кож.складка бедро (мм)")
    skinfold_triceps: Optional[int] = Field(None, ge=0, le=100, description="Кож.складка трицепс (мм)")
    skinfold_subscapular: Optional[int] = Field(None, ge=0, le=100, description="Кож.складка под лопаткой (мм)")

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
    time_slot: str = Field(..., description="УТРО/ДЕНЬ/ВЕЧЕР")
    format_name: str = Field(..., description="VIP/Double/Group")
    package_size: int = Field(..., ge=1)
