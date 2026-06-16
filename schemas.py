"""Pydantic схемы для документации / валидации."""

from datetime import datetime

import pydantic
from pydantic import BaseModel


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
