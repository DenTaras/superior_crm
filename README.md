# SUPERIOR CRM

CRM для студии персонального тренинга SUPERIOR. Серверная часть — FastAPI + SQLAlchemy, шаблоны — Jinja2.

## Технологии

- **Python 3.13**, **FastAPI**
- **SQLAlchemy** (синхронный ORM)
- **SQLite** (по умолчанию) / **PostgreSQL** (через `DATABASE_URL`)
- **Alembic** — миграции схемы БД
- **Pydantic** — валидация форм
- **ruff** — линтинг
- **pytest** — 78 тестов
- **GitHub Actions** — CI (lint + test + migrations)

## Быстрый запуск (SQLite)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app:app --reload
```

Открыть: http://127.0.0.1:8000/

## Запуск с PostgreSQL

```powershell
$env:DATABASE_URL="postgresql://user:pass@localhost:5432/superior_crm"
python -m alembic upgrade head
uvicorn app:app --reload
```

## Модели данных

| Таблица | Назначение |
|---------|-----------|
| `clients` | Клиенты: ФИО, телефон, `remaining_sessions` |
| `slots` | Слоты расписания: время начала, вместимость |
| `bookings` | Бронирования: уникальный ключ `(slot_id, client_id)` |
| `journal` | Журнал проведённых занятий + комментарии (JSON) |
| `training_notes` | Рабочие заметки по клиентам (удаляются при завершении) |

## Функционал

### Клиенты (`/clients`)
- Создание, редактирование, удаление клиента
- Фильтрация по имени и телефону
- **Пагинация** (25 на странице)
- Покупка абонемента (4/8/12 занятий)
- Блокировка записи, если `remaining_sessions == 0`

### Расписание (`/schedule`)
- Недельный календарь 08:00–22:00
- Навигация по неделям (`week_offset`)
- Создание одиночного / массового слота (по интервалу)
- Массовое удаление слотов по интервалу
- Защита от пересечения слотов (1-часовая длительность)
- Запрет создания слота в прошлом

### Слот (`/slot/{id}`)
- Просмотр клиентов в слоте
- Добавление / удаление клиента
- Проверка вместимости
- `select_for_update` — защита от гонок при бронировании
- `UNIQUE (slot_id, client_id)` — защита дубликатов на уровне БД

### Программа тренировки (`/slot/{id}/program`)
- Список клиентов с переключением по клику
- Редактирование заметки для каждого клиента
- **Автосохранение** — 300ms debounce + sendBeacon при навигации
- Только data-атрибуты (чистый JS, никакого Jinja2 внутри скриптов)
- Подтверждение занятия → заметки в журнал, списание `remaining_sessions`

### Журнал (`/journal`)
- Список проведённых занятий с комментариями
- Переносы строк в комментариях сохраняются

### Абонементы (`/subscriptions`)
- Пакеты: 12, 8, 4 занятия
- Пополнение через карточку клиента

## Безопасность и надёжность

- **Валидация форм** — Pydantic (422 при невалидных данных)
- **UNIQUE constraint** на `bookings(slot_id, client_id)` — дубликаты невозможны на уровне БД
- **Row-level lock** — `select_for_update` при бронировании
- **Retry** — до 3 повторов при `IntegrityError`
- **XSS-экранирование** — Jinja2 + дополнительная проверка в тестах
- **SQLi-безопасность** — параметризованные запросы через SQLAlchemy

## Тесты

```powershell
pytest -q              # 78 тестов
ruff check .           # линтинг
```

Наборы тестов:
| Файл | Что проверяет |
|------|--------------|
| `test_bookings.py` | capacity, дубликаты, DB constraint, очистка notes |
| `test_calendar.py` | отображение недели, week_offset |
| `test_clients.py` | CRUD, пагинация |
| `test_edge_cases.py` | XSS, SQLi, граничные значения (33 теста) |
| `test_journal.py` | завершение слота, декремент, страница журнала |
| `test_optimization.py` | тайминги (150 слотов, 100 записей, bulk) |
| `test_program.py` | save + persist, HTML-level проверка |
| `test_slots.py` | конфликты, прошлое |
| `test_subscriptions.py` | абонементы, лимиты |

## Миграции (Alembic)

```powershell
python -m alembic revision --autogenerate -m "описание"
python -m alembic upgrade head
python -m alembic downgrade -1
python -m alembic history
```

## Структура проекта

```
superior_crm/
├── app.py                  # Точка входа (FastAPI app + seed)
├── models.py               # SQLAlchemy модели
├── database.py             # Engine, Session, get_db, templates
├── schemas.py              # Pydantic схемы (данные + формы)
├── forms.py                # Depends-функции Form→Pydantic
├── pyproject.toml          # Конфиг ruff + pytest
├── .github/workflows/      # CI (GitHub Actions)
├── alembic/                # Миграции
│   ├── env.py
│   └── versions/
├── routes/
│   ├── clients.py          # /clients
│   ├── schedule.py         # /schedule, /slot/{id}
│   ├── slots.py            # /slots/*, /slot/{id}/add|complete
│   ├── program.py          # /slot/{id}/program
│   └── journal.py          # /, /journal, /subscriptions
├── templates/              # Jinja2 шаблоны (9 файлов)
├── static/style.css
├── tests/                  # 9 файлов, 78 тестов
├── requirements.txt
└── README.md
```

## Стилизация

Основной CSS — `static/style.css`. Переменные `:root` для быстрой настройки темы. Используйте DevTools → Disable cache при разработке.
