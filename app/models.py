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
    goal = Column(String, nullable=True)             # lose | gain | recompose
    activity_level = Column(String, nullable=True)   # sedentary | light | moderate | active | extreme
    pd_consent_given = Column(Boolean, default=False)
    pd_consent_at = Column(DateTime, nullable=True)
    frozen_until = Column(DateTime, nullable=True)        # заморожен до (заморозка стрика)
    freeze_days_remaining = Column(Integer, default=0)    # осталось дней заморозки
    last_freeze_cd = Column(DateTime, nullable=True)       # кулдаун разморозки (24ч)

    def fio(self) -> str:
        """Краткое ФИО: «Фамилия Имя» или fallback на `name`."""
        parts = [p for p in [self.last_name, self.first_name, self.patronymic] if p]
        if parts:
            return " ".join(parts)
        return (self.name or "").strip()


class Slot(Base):
    """Слот расписания (тренировка на 1 час)."""
    __tablename__ = "slots"
    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime)
    capacity = Column(Integer, default=4)
    completed = Column(Boolean, default=False)


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
    pd_consent = Column(Boolean, default=False)
    pd_consent_at = Column(DateTime, nullable=True)


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


class FoodRestriction(Base):
    """Продукт/категория, которую клиент исключает из рациона."""
    __tablename__ = "food_restrictions"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    tag = Column(String, nullable=False)  # "молоко" | "свинина" | "глютен" | "орехи"


class MealTemplate(Base):
    """Шаблон приёма пищи."""
    __tablename__ = "meal_templates"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    meal_type = Column(String, nullable=False)  # breakfast | snack | lunch | dinner
    course = Column(String, nullable=True)       # main | first | drink
    calories = Column(Integer, default=0)
    protein = Column(Integer, default=0)
    fat = Column(Integer, default=0)
    carbs = Column(Integer, default=0)
    weight_g = Column(Integer, default=0)
    tags = Column(Text, nullable=True)        # JSON: ["молоко","орехи"]
    ingredients = Column(Text, nullable=True)  # список продуктов на порцию
    recipe = Column(Text, nullable=True)       # краткое описание приготовления
    sort_order = Column(Integer, default=0)


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
    freeze_days_remaining = Column(Integer, default=0)  # дней заморозки в этом пакете


class SubscriptionConsumption(Base):
    """Списание одного занятия по абонементу."""
    __tablename__ = "subscription_consumptions"
    id = Column(Integer, primary_key=True)
    purchase_id = Column(Integer, ForeignKey("subscription_purchases.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    slot_id = Column(Integer, ForeignKey("slots.id"), nullable=True)
    slot_time = Column(DateTime, nullable=True)       # когда прошла тренировка
    created_at = Column(DateTime, default=datetime.now)


class Product(Base):
    """Продукт питания."""
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    category = Column(String, nullable=False)  # meat | poultry | fish | dairy | eggs | vegetables | fruit | groceries | seasoning | other
    unit = Column(String, default="г")          # г | мл | шт


class MealProduct(Base):
    """Связь шаблона блюда с продуктом + количество."""
    __tablename__ = "meal_products"
    id = Column(Integer, primary_key=True)
    meal_template_id = Column(Integer, ForeignKey("meal_templates.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)      # в единицах product.unit


class Employee(Base):
    """Сотрудник студии (тренер, директор)."""
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, default="")
    patronymic = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    position = Column(String, nullable=False)       # director | trainer | admin
    login = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    salary_type = Column(String, default="fixed")   # fixed | fixed+bonus | fixed+dividends
    salary_amount = Column(Integer, default=0)       # оклад руб/мес
    regional_coefficient = Column(Integer, default=100)  # районный коэффициент в % (100=1.0, 115=1.15)
    bonus_percent = Column(Integer, nullable=True)   # премия % от выручки
    dividend_percent = Column(Integer, nullable=True) # дивиденды % от чистой прибыли
    created_at = Column(DateTime, default=datetime.now)

    def fio(self) -> str:
        parts = [p for p in [self.last_name, self.first_name, self.patronymic] if p]
        return " ".join(parts) or "—"


class SlotEmployee(Base):
    """Назначение тренера на слот."""
    __tablename__ = "slot_employees"
    id = Column(Integer, primary_key=True)
    slot_id = Column(Integer, ForeignKey("slots.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    assigned_at = Column(DateTime, default=datetime.now)

class Achievement(Base):
    """Достижение клиента (геймификация)."""
    __tablename__ = "achievements"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    category = Column(String, nullable=False)        # strength | body | discipline | rank
    icon = Column(String, default="🏆")               # эмодзи
    title = Column(String, nullable=False)            # заголовок
    description = Column(String, default="")          # описание
    achieved_at = Column(DateTime, default=datetime.now)


class FreezeLog(Base):
    """Лог дней заморозки (для сохранения стрика)."""
    __tablename__ = "freeze_log"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    date = Column(DateTime, nullable=False)            # день, который засчитывается как непрерывность
    reason = Column(String, default="freeze")          # freeze | unfreeze
    created_at = Column(DateTime, default=datetime.now)

class Payment(Base):
    """Платёж через онлайн-эквайринг."""
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)                       # сумма в копейках
    currency = Column(String, default="RUB")
    description = Column(String, default="")
    provider = Column(String, default="yookassa")                  # yookassa | tinkoff | sber
    provider_payment_id = Column(String, nullable=True)            # ID платежа в ПШ
    status = Column(String, default="pending")                      # pending | succeeded | cancelled | refunded
    metadata_json = Column(Text, nullable=True)                     # JSON: time_slot, format, package_size
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class Expense(Base):
    """Статья расходов."""
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    month = Column(String, nullable=False, index=True)      # "2026-06"
    category = Column(String, nullable=False)                # salary | tax_ndfl | tax_social | tax_usn | rent | other
    description = Column(String, default="")
    amount = Column(Integer, nullable=False)                 # в рублях
    created_at = Column(DateTime, default=datetime.now)
