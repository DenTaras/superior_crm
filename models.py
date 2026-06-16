"""Модели данных SQLAlchemy."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Client(Base):
    """Клиент студии."""
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    patronymic = Column(String, nullable=True)
    birth_year = Column(Integer, nullable=True)
    birth_place = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    name = Column(String, nullable=True)          # legacy — полное имя одной строкой
    remaining_sessions = Column(Integer, default=1)

    def fio(self) -> str:
        """Краткое ФИО: «Фамилия Имя» или fallback на `name`."""
        parts = []
        if self.last_name:
            parts.append(self.last_name)
        if self.first_name:
            parts.append(self.first_name)
        if self.patronymic:
            parts.append(self.patronymic)
        if parts:
            return " ".join(parts)
        return (self.name or "").strip()


class Slot(Base):
    """Слот расписания (тренировка на 1 час)."""
    __tablename__ = "slots"
    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime)
    capacity = Column(Integer, default=4)


class Booking(Base):
    """Бронирование — связь клиента со слотом."""
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    slot_id = Column(Integer, ForeignKey("slots.id"))


class JournalEntry(Base):
    """Запись в журнале проведённых занятий."""
    __tablename__ = "journal"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.now)
    slot_time = Column(DateTime)
    clients = Column(String)                      # имена через запятую
    comments = Column(String, nullable=True)      # JSON: client_id -> текст


class TrainingNote(Base):
    """Рабочая заметка по клиенту в рамках слота (удаляется при завершении)."""
    __tablename__ = "training_notes"
    id = Column(Integer, primary_key=True)
    slot_id = Column(Integer, ForeignKey("slots.id"), index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), index=True)
    text = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.now)
