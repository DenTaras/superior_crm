"""Модели данных SQLAlchemy."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint, create_engine
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
    height_cm = Column(Integer, nullable=True)
    weight_kg = Column(Integer, nullable=True)
    body_fat = Column(Integer, nullable=True)  # % жира
    login = Column(String, unique=True, nullable=True)
    password_hash = Column(String, nullable=True)

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
    __table_args__ = (
        UniqueConstraint('slot_id', 'client_id', name='uq_booking_slot_client'),
    )
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


class TrainingRequest(Base):
    """Заявка на пробную тренировку от незарегистрированного пользователя."""
    __tablename__ = "training_requests"
    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, default="")
    phone = Column(String, default="")
    goal = Column(String, default="")              # цель тренировок
    preferred_time = Column(String, default="")    # предпочитаемое время
    created_at = Column(DateTime, default=datetime.now)


class ExerciseGroup(Base):
    """Группа упражнений (СПИНА, ГРУДЬ, НОГИ и т.д.)."""
    __tablename__ = "exercise_groups"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    sort_order = Column(Integer, default=0)


class Exercise(Base):
    """Конкретное упражнение."""
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("exercise_groups.id"), nullable=False)
    name = Column(String, nullable=False)
    sort_order = Column(Integer, default=0)


class ClientExerciseLog(Base):
    """Лог выполнения упражнения клиентом (история для прогрессии)."""
    __tablename__ = "client_exercise_log"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    weight = Column(Integer, default=0)           # вес отягощения в кг
    reps = Column(Integer, default=0)             # фактическое количество повторений
    sets = Column(Integer, default=0)             # количество подходов
    created_at = Column(DateTime, default=datetime.now)


class TrainingPlanExercise(Base):
    """Упражнение в плане тренировки для клиента в рамках слота."""
    __tablename__ = "training_plan_exercises"
    id = Column(Integer, primary_key=True)
    slot_id = Column(Integer, ForeignKey("slots.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    weight = Column(Integer, default=0)           # вес отягощения в кг
    target_reps = Column(Integer, default=0)      # целевое количество повторений
    actual_reps = Column(Integer, nullable=True)  # фактическое (заполняет тренер)
    sets = Column(Integer, default=0)             # количество подходов
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
