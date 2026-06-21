"""Модели данных SQLAlchemy."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, UniqueConstraint, create_engine
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
    height_cm = Column(Integer, nullable=True)
    weight_kg = Column(Integer, nullable=True)
    body_fat = Column(Integer, nullable=True)  # % жира
    hip_cm = Column(Integer, nullable=True)       # обхват бедра
    waist_cm = Column(Integer, nullable=True)     # обхват талии
    chest_cm = Column(Integer, nullable=True)     # обхват груди
    shoulders_cm = Column(Integer, nullable=True) # обхват плеч
    biceps_cm = Column(Integer, nullable=True)    # обхват бицепса
    neck_cm = Column(Integer, nullable=True)       # обхват шеи
    wrist_cm = Column(Integer, nullable=True)      # обхват запястья (для типа телосложения)
    skinfold_chest = Column(Integer, nullable=True)     # калипер: грудь (мм)
    skinfold_abdominal = Column(Integer, nullable=True) # калипер: живот (мм)
    skinfold_thigh = Column(Integer, nullable=True)     # калипер: бедро (мм)
    skinfold_triceps = Column(Integer, nullable=True)   # калипер: трицепс (мм)
    skinfold_subscapular = Column(Integer, nullable=True) # калипер: под лопаткой (мм)
    login = Column(String, unique=True, nullable=True)
    password_hash = Column(String, nullable=True)
    photo_path = Column(String, nullable=True)   # путь к фото относительно static/
    sex = Column(String, nullable=True)            # m/f

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


class AnthropometryLog(Base):
    """Лог изменения антропометрии клиента (для графика прогресса)."""
    __tablename__ = "anthropometry_log"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now)
    height_cm = Column(Integer, nullable=True)
    weight_kg = Column(Integer, nullable=True)
    body_fat = Column(Integer, nullable=True)
    hip_cm = Column(Integer, nullable=True)
    waist_cm = Column(Integer, nullable=True)
    chest_cm = Column(Integer, nullable=True)
    shoulders_cm = Column(Integer, nullable=True)
    biceps_cm = Column(Integer, nullable=True)
    neck_cm = Column(Integer, nullable=True)
    wrist_cm = Column(Integer, nullable=True)
    skinfold_chest = Column(Integer, nullable=True)
    skinfold_abdominal = Column(Integer, nullable=True)
    skinfold_thigh = Column(Integer, nullable=True)
    skinfold_triceps = Column(Integer, nullable=True)
    skinfold_subscapular = Column(Integer, nullable=True)


class SubscriptionPurchase(Base):
    """Покупка абонемента клиентом."""
    __tablename__ = "subscription_purchases"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    time_slot = Column(String, nullable=False)
    format_name = Column(String, nullable=False)
    package_size = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)
    remaining = Column(Integer, default=0)           # осталось занятий по этому пакету
    refunded = Column(Boolean, default=False)        # полный возврат
    refunded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class SubscriptionConsumption(Base):
    """Списание одного занятия по абонементу."""
    __tablename__ = "subscription_consumptions"
    id = Column(Integer, primary_key=True)
    purchase_id = Column(Integer, ForeignKey("subscription_purchases.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    slot_id = Column(Integer, ForeignKey("slots.id"), nullable=True)
    slot_time = Column(DateTime, nullable=True)       # когда прошла тренировка
    created_at = Column(DateTime, default=datetime.now)
