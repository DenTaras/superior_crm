from datetime import datetime, timedelta
from typing import Generator, List

from fastapi import FastAPI
from fastapi import Request
from fastapi import Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

import pydantic
from pydantic import BaseModel

from sqlalchemy import *
from sqlalchemy.orm import *
from sqlalchemy.orm import Session

# Файл app.py - основной файл приложения, который содержит все маршруты и логику работы с базой данных. 
# Здесь мы определяем модели данных, создаем базу данных и реализуем маршруты для отображения расписания, 
# страницы слота и добавления клиента в слот.
app = FastAPI()
# Подключаем статические файлы (например, CSS) из папки "static"
app.mount("/static", StaticFiles(directory="static"), name="static")
# Настраиваем Jinja2Templates для рендеринга HTML-шаблонов из папки "templates"
templates = Jinja2Templates(directory="templates")
# Настраиваем SQLAlchemy для работы с базой данных SQLite. 
# Мы создаем движок базы данных, определяем базовый класс для моделей и создаем сессию 
# для взаимодействия с базой данных.
engine = create_engine(
    "sqlite:///superior.db",
    connect_args={"check_same_thread": False},
)
# Определяем модели данных для клиентов, слотов и бронирований.
Base = declarative_base()
# Создаем сессию для взаимодействия с базой данных
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Фабрика зависимостей для получения сессии базы данных.

    Возвращает генератор, который предоставляет инстанс `Session` и гарантированно
    закрывает сессию при завершении запроса.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Модель данных для клиентов, которая содержит поля id, name и phone.
class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    # Подробные поля клиента
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    patronymic = Column(String, nullable=True)
    birth_year = Column(Integer, nullable=True)
    birth_place = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    # legacy поле `name` сохраняем для обратной совместимости
    name = Column(String, nullable=True)

    def fio(self) -> str:
        """Возвращает краткое ФИО клиента: "Фамилия Имя Отчество" или fallback на `name`.

        Используется для кратких отображений по всему приложению.
        """
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

# Модель данных для слотов, которая содержит поля id, start_time и capacity.
class Slot(Base):
    __tablename__ = "slots"
    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime)
    capacity = Column(Integer, default=4)

# Модель данных для бронирований, которая содержит поля id, client_id и slot_id.
class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    slot_id = Column(Integer, ForeignKey("slots.id"))

# Создаем все таблицы в базе данных, если они еще не существуют.
Base.metadata.create_all(engine)

# Для существующей SQLite БД: добавляем недостающие колонки в таблицу clients,
# чтобы обновление модели не ломало приложение при локальной разработке.
def ensure_client_columns():
    """Проверяет и добавляет отсутствующие колонки в таблицу `clients`.

    Утилита полезна при локальной разработке: если модель `Client` была
    расширена, но в существующей SQLite базе нет колонок, функция выполнит
    `ALTER TABLE` для добавления недостающих полей (мягко, без критических ошибок).
    """
    with engine.connect() as conn:
        res = conn.execute(text("PRAGMA table_info(clients)"))
        existing = [row[1] for row in res.fetchall()]
        to_add = [
            ("first_name", "TEXT"),
            ("last_name", "TEXT"),
            ("patronymic", "TEXT"),
            ("birth_year", "INTEGER"),
            ("birth_place", "TEXT"),
            ("phone", "TEXT"),
            ("name", "TEXT"),
        ]
        for col, coltype in to_add:
            if col not in existing:
                try:
                    conn.execute(text(f"ALTER TABLE clients ADD COLUMN {col} {coltype}"))
                except Exception:
                    # если что-то пошло не так — пропускаем, можно логировать
                    pass


ensure_client_columns()


# Регистрируем Jinja2 фильтр для форматирования телефонов
def format_phone(value: str) -> str:
    """Преобразует номер телефона в читаемый вид: +79990000001 -> +7 999 000 00 01"""
    if not value:
        return ""
    s = ''.join(ch for ch in value if ch.isdigit())
    # Ожидаем 11 цифр для российского номера
    if len(s) == 11 and s.startswith('7'):
        return f"+7 {s[1:4]} {s[4:7]} {s[7:9]} {s[9:11]}"
    # fallback: группировать по 3/2
    if len(s) >= 10:
        return f"+{s[:-10]} {s[-10:-7]} {s[-7:-4]} {s[-4:-2]} {s[-2:]}"
    return value

templates.env.filters['format_phone'] = format_phone


# Pydantic схемы (базовые для документации/валидации)
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

# Настройка совместимости с Pydantic v1/v2: если установлена v2, используем `model_config`,
# иначе оставляем старый `Config.orm_mode`.
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

# Главная страница (информационная)
@app.get("/")
def home(request: Request):
    """Главная информационная страница проекта."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request},
    )


# Маршрут для отображения расписания. Здесь мы извлекаем все слоты из базы данных,
# считаем количество бронирований для каждого слота и передаем эту информацию в 
# шаблон "schedule.html" для отображения.
@app.get("/schedule")
def schedule(request: Request, db: Session = Depends(get_db), week_offset: int = 0):
    """Генерирует вид расписания в виде календаря на текущую неделю (понедельник-воскресенье)

    Возвращает структуру с сутками недели и часовыми интервалами. Слоты сопоставляются по дате и часу начала.
    """
    # получаем все слоты за ближайшую неделю (можно оптимизировать)
    slots = db.query(Slot).order_by(Slot.start_time).all()

    now = datetime.now()
    # начало недели (понедельник) с учётом смещения недель
    base_week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = base_week_start + timedelta(days=7 * week_offset)
    days = [week_start + timedelta(days=i) for i in range(7)]
    # часы от 08:00 до 22:00 включительно
    hours = list(range(8, 23))

    default_time = datetime.now().strftime("%Y-%m-%dT%H:%M")

    # карту ячеек: (day_index, hour) -> slot or None
    grid = {(d_idx, h): None for d_idx in range(7) for h in hours}

    for slot in slots:
        if not slot.start_time:
            continue
        slot_dt = slot.start_time
        # сравниваем дату (без времени)
        delta = slot_dt.date() - week_start.date()
        if delta.days < 0 or delta.days >= 7:
            continue
        day_index = delta.days
        hour = slot_dt.hour
        if hour in hours:
            # соберём список клиентов, записанных в слот
            bookings = db.query(Booking).filter(Booking.slot_id == slot.id).all()
            clients_in_slot = [db.get(Client, b.client_id) for b in bookings]
            grid[(day_index, hour)] = {
                'slot': slot,
                'booked': len(clients_in_slot),
                'clients': clients_in_slot,
            }

    return templates.TemplateResponse(
        request=request,
        name="schedule.html",
        context={
            "days": days,
            "hours": hours,
            "grid": grid,
            "default_time": default_time,
            "week_offset": week_offset,
        },
    )

# Маршрут для отображения страницы слота. Здесь мы извлекаем информацию о слоте и всех клиентах, 
# которые забронировали этот слот, а также всех клиентов из базы данных.
@app.get("/slot/{slot_id}")
def slot_page(
    request: Request,
    slot_id: int,
    db: Session = Depends(get_db),
    week_offset: int = 0,
):
    """Страница отдельного слота: показывает список записанных клиентов

    Параметры:
    - `slot_id`: идентификатор слота
    - `week_offset`: смещение недели для возврата к календарю
    """
    slot = db.get(Slot, slot_id)
    bookings = (
        db.query(Booking)
        .filter(
            Booking.slot_id == slot_id
        )
        .all()
    )

    clients: List[Client] = []

    for booking in bookings:
        clients.append(
            db.get(
                Client,
                booking.client_id,
            )
        )

    all_clients = db.query(Client).all()

    return templates.TemplateResponse(
        request=request,
        name="slot.html",
        context={
            "slot": slot,
            "clients": clients,
            "all_clients": all_clients,
            "week_offset": week_offset,
        },
    )


@app.get("/clients")
def clients_page(
    request: Request,
    db: Session = Depends(get_db),
    q_name: str = "",
    q_phone: str = "",
):
    """Clients list with optional server-side filtering by name and phone.

    Query params:
    - q_name: partial match against `name`, `first_name` or `last_name` (case-insensitive)
    - q_phone: partial match against `phone` (digits or formatted)

    The resulting table in the template is constrained to a fixed-height scroll window.
    """
    query = db.query(Client)
    # фильтр по имени (частичный, case-insensitive)
    if q_name:
        pat = f"%{q_name}%"
        query = query.filter(
            or_(
                Client.name.ilike(pat),
                Client.first_name.ilike(pat),
                Client.last_name.ilike(pat),
            )
        )

    # фильтр по телефону — ищем по цифрам или по введённой подстроке
    if q_phone:
        digits = ''.join(ch for ch in q_phone if ch.isdigit())
        if digits:
            query = query.filter(Client.phone.ilike(f"%{digits}%") | Client.phone.ilike(f"%{q_phone}%"))
        else:
            query = query.filter(Client.phone.ilike(f"%{q_phone}%"))

    clients = query.order_by(Client.last_name, Client.first_name).limit(1000).all()

    return templates.TemplateResponse(
        request=request,
        name="clients.html",
        context={
            "clients": clients,
            "q_name": q_name,
            "q_phone": q_phone,
        },
    )


@app.post("/clients/create")
def add_client_post(
    first_name: str = Form(...),
    last_name: str = Form(""),
    patronymic: str = Form(""),
    birth_year: int = Form(None),
    birth_place: str = Form(""),
    phone: str = Form(""),
    db: Session = Depends(get_db),
):
    """Обрабатывает POST-запрос создания нового клиента.

    Валидирует минимально нужные поля и сохраняет нового клиента в БД,
    затем перенаправляет на список клиентов.
    """
    first_name = (first_name or "").strip()
    if not first_name:
        return RedirectResponse("/clients", status_code=303)

    client = Client(
        first_name=first_name,
        last_name=(last_name or "").strip(),
        patronymic=(patronymic or "").strip(),
        birth_year=birth_year,
        birth_place=(birth_place or "").strip(),
        phone=(phone or "").strip(),
        name=f"{(last_name or '').strip()} {(first_name or '').strip()}".strip(),
    )
    db.add(client)
    db.commit()

    return RedirectResponse("/clients", status_code=303)


@app.get("/clients/edit/{client_id}")
def clients_edit(request: Request, client_id: int, db: Session = Depends(get_db)):
    """Отображает форму редактирования существующего клиента.

    Если клиент не найден — перенаправляет на список клиентов.
    """
    client = db.get(Client, client_id)
    if client is None:
        return RedirectResponse("/clients", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="clients_edit.html",
        context={"client": client},
    )


@app.get("/clients/create")
def clients_create(request: Request):
    """Пустая форма для создания нового клиента."""
    return templates.TemplateResponse(
        request=request,
        name="clients_create.html",
        context={},
    )


@app.post("/clients/edit/{client_id}")
def clients_edit_post(
    client_id: int,
    first_name: str = Form(...),
    last_name: str = Form(""),
    patronymic: str = Form(""),
    birth_year: int = Form(None),
    birth_place: str = Form(""),
    phone: str = Form(""),
    db: Session = Depends(get_db),
):
    """Обновляет данные клиента по POST-запросу и сохраняет изменения.

    При успешном обновлении перенаправляет обратно на список клиентов.
    """
    client = db.get(Client, client_id)
    if client:
        client.first_name = (first_name or "").strip()
        client.last_name = (last_name or "").strip()
        client.patronymic = (patronymic or "").strip()
        client.birth_year = birth_year
        client.birth_place = (birth_place or "").strip()
        client.phone = (phone or "").strip()
        client.name = f"{client.last_name} {client.first_name}".strip()
        db.add(client)
        db.commit()

    return RedirectResponse("/clients", status_code=303)


@app.post("/clients/delete/{client_id}")
def clients_delete(client_id: int, db: Session = Depends(get_db)):
    """Удаляет клиента и его связанные бронирования из базы данных.

    Операция идёт в две стадии: удаление записей из `bookings`, затем удаление
    самого клиента.
    """
    # удаляем связанные бронирования, затем клиента
    db.query(Booking).filter(Booking.client_id == client_id).delete()
    db.query(Client).filter(Client.id == client_id).delete()
    db.commit()
    return RedirectResponse("/clients", status_code=303)





@app.post("/slots/add")
def slots_add(
    start_time: str = Form(...),
    capacity: int = Form(1),
    week_offset: int = Form(0),
    db: Session = Depends(get_db),
):
    """Создаёт новый часовой слот.

    Проверяет формат времени, нормализует `capacity` и запрещает создание
    перекрывающегося слота (слот длится 1 час). При конфликте возвращает
    редирект с флаш-сообщением.
    """
    # ожидается ISO формат: YYYY-MM-DDTHH:MM или YYYY-MM-DD HH:MM
    ts = start_time.replace(" ", "T")
    start = datetime.fromisoformat(ts)
    try:
        capacity = int(capacity)
    except Exception:
        capacity = 1
    if capacity not in (1, 2, 3, 4):
        capacity = 1
    # проверка перекрытия: слот длится 1 час; запрещаем пересечение
    new_start = start
    new_end = new_start + timedelta(hours=1)
    overlapping = (
        db.query(Slot)
        .filter(Slot.start_time > (new_start - timedelta(hours=1)), Slot.start_time < new_end)
        .all()
    )
    if overlapping:
        # не создаём слот, возвращаемся на страницу расписания с флаш-сообщением
        return RedirectResponse(f"/schedule?week_offset={week_offset}&flash=slot_conflict", status_code=303)
    slot = Slot(start_time=start, capacity=capacity)
    db.add(slot)
    db.commit()
    return RedirectResponse(f"/schedule?week_offset={week_offset}", status_code=303)





@app.post("/slots/edit/{slot_id}")
def slots_edit_post(
    slot_id: int,
    start_time: str = Form(...),
    capacity: int = Form(1),
    week_offset: int = Form(0),
    db: Session = Depends(get_db),
):
    """Обрабатывает редактирование слота: меняет время и вместимость.

    Выполняет проверку на пересечение с другими слотами (1-часовая длительность).
    При конфликте делает редирект с флаш-уведомлением.
    """
    slot = db.get(Slot, slot_id)
    if slot:
        ts = start_time.replace(" ", "T")
        new_start = datetime.fromisoformat(ts)
        new_end = new_start + timedelta(hours=1)
        overlapping = (
            db.query(Slot)
            .filter(Slot.id != slot_id, Slot.start_time > (new_start - timedelta(hours=1)), Slot.start_time < new_end)
            .all()
        )
        if overlapping:
            return RedirectResponse(f"/schedule?week_offset={week_offset}&flash=slot_conflict", status_code=303)
        slot.start_time = new_start
        try:
            capacity = int(capacity)
        except Exception:
            capacity = 1
        if capacity not in (1, 2, 3, 4):
            capacity = 1
        slot.capacity = capacity
        db.add(slot)
        db.commit()
    return RedirectResponse(f"/schedule?week_offset={week_offset}", status_code=303)


@app.post("/slots/delete/{slot_id}")
def slots_delete(slot_id: int, week_offset: int = Form(0), db: Session = Depends(get_db)):
    """Удаляет слот и все связанные с ним бронирования, затем перенаправляет
    обратно в календарь с сохранением `week_offset`.
    """
    # удалить бронирования в слоте, затем слот
    db.query(Booking).filter(Booking.slot_id == slot_id).delete()
    db.query(Slot).filter(Slot.id == slot_id).delete()
    db.commit()
    return RedirectResponse(f"/schedule?week_offset={week_offset}", status_code=303)


@app.post("/slot/{slot_id}/remove")
def remove_booking(slot_id: int, client_id: int = Form(...), week_offset: int = Form(0), db: Session = Depends(get_db)):
    """Удаляет конкретную запись клиента из слота.

    Параметры: `slot_id`, `client_id`. После удаления перенаправляет на страницу слота.
    """
    db.query(Booking).filter(Booking.slot_id == slot_id, Booking.client_id == client_id).delete()
    db.commit()
    return RedirectResponse(f"/slot/{slot_id}?week_offset={week_offset}", status_code=303)


@app.post("/slot/{slot_id}/add")
def add_client(
    slot_id: int,
    client_id: int = Form(...),
    week_offset: int = Form(0),
    db: Session = Depends(get_db),
):
    """Добавляет клиента в слот через POST-запрос.

    Проверяет вместимость слота и не добавляет запись, если слот заполнен.
    """
    slot = db.get(Slot, slot_id)

    count = (
        db.query(Booking)
        .filter(
            Booking.slot_id == slot.id
        )
        .count()
    )

    if count < slot.capacity:

        booking = Booking(
            client_id=client_id,
            slot_id=slot.id,
        )

        db.add(booking)
        db.commit()

    return RedirectResponse(f"/slot/{slot_id}?week_offset={week_offset}", status_code=303)


# При первом запуске приложения мы проверяем, есть ли в базе данных клиенты и слоты. 
# Если их нет, то мы добавляем несколько клиентов и слотов для тестирования.
db = SessionLocal()
try:
    if db.query(Client).count() == 0:

        db.add_all([
            Client(
                first_name="Иван",
                last_name="Петров",
                patronymic="",
                birth_year=1985,
                birth_place="Москва",
                phone="+79990000001",
                name="Петров Иван",
            ),
            Client(
                first_name="Мария",
                last_name="Иванова",
                patronymic="",
                birth_year=1990,
                birth_place="Санкт-Петербург",
                phone="+79990000002",
                name="Иванова Мария",
            ),
            Client(
                first_name="Алексей",
                last_name="Сидоров",
                patronymic="",
                birth_year=1988,
                birth_place="Казань",
                phone="+79990000003",
                name="Сидоров Алексей",
            ),
        ])
        for i in range(9):
            db.add_all([
                Client(
                    first_name=f"{i}",
                    last_name=f"{i}",
                    patronymic="",
                    birth_year=1985,
                    birth_place=f"{i}",
                    phone="+79990000001",
                    name=f"{i}",
                )
            ])
        db.commit()

    if db.query(Slot).count() == 0:

        now = datetime.now()

        db.add_all([
            Slot(
                start_time=now + timedelta(hours=1),
                capacity=1,
            ),
            Slot(
                start_time=now + timedelta(hours=2),
                capacity=2,
            ),
            Slot(
                start_time=now + timedelta(hours=3),
                capacity=4,
            ),
        ])

        db.commit()
finally:
    db.close()