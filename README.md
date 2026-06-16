# SUPERIOR CRM

CRM для студии персонального тренинга SUPERIOR. Серверная часть — FastAPI + SQLAlchemy, шаблоны — Jinja2.

## Технологии

- **Python 3.13**, **FastAPI**
- **SQLAlchemy** (синхронный ORM)
- **SQLite** (по умолчанию, для локальной разработки) / **PostgreSQL** (через переменную окружения)
- **Alembic** — миграции схемы БД
- **Jinja2 templates**, **CSS** в `static/style.css`
- **pytest** — тесты (18 тестов)

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
| `clients` | Клиенты: ФИО, телефон, год рождения, `remaining_sessions` |
| `slots` | Слоты расписания: время начала, вместимость |
| `bookings` | Бронирования: связь клиента со слотом |
| `journal` | Журнал проведённых занятий + комментарии тренера |
| `training_notes` | Рабочие заметки по клиентам (удаляются при завершении) |

## Функционал

### Клиенты (`/clients`)
- Создание, редактирование, удаление клиента
- Фильтрация по имени и телефону
- Покупка абонемента (4/8/12 занятий) — увеличивает `remaining_sessions`
- Блокировка записи, если `remaining_sessions == 0`

### Расписание (`/schedule`)
- Недельный календарь 08:00–22:00 с понедельника по воскресенье
- Навигация по неделям (`week_offset`)
- Создание одиночного или массового слота (по интервалу)
- Массовое удаление слотов по интервалу
- Защита от пересечения слотов (1-часовая длительность)
- Запрет создания/переноса слота в прошлое

### Слот (`/slot/{id}`)
- Просмотр записанных клиентов
- Добавление/удаление клиента со слотом
- Проверка вместимости слота
- Защита от дублирующейся записи

### Программа тренировки (`/slot/{id}/program`)
- Список клиентов в слоте
- Поэтапное редактирование заметки для каждого клиента
- Автосохранение (300ms debounce, sendBeacon при навигации)
- Подтверждение занятия → перенос заметок в журнал, списание `remaining_sessions`

### Журнал (`/journal`)
- Список проведённых занятий с комментариями тренера
- Перенос строк в комментариях отображается корректно

### Абонементы (`/subscriptions`)
- Пакеты: 12, 8, 4 занятия
- Пополнение через карточку клиента

## Тесты

```powershell
pytest -q
# или с покрытием:
pytest tests/ --cov=. --cov-report=term-missing
```

## Миграции (Alembic)

```powershell
# Создать новую миграцию после изменения моделей
python -m alembic revision --autogenerate -m "описание"

# Применить миграции
python -m alembic upgrade head

# Откатить последнюю
python -m alembic downgrade -1

# Посмотреть историю
python -m alembic history
```

## Структура проекта

```
superior_crm/
├── app.py                  # Основное приложение (маршруты, модели, БД)
├── alembic.ini             # Конфиг Alembic
├── alembic/                # Миграции
│   ├── env.py              # Настройка окружения Alembic
│   └── versions/           # Файлы миграций
├── templates/              # Jinja2 шаблоны
│   ├── base.html
│   ├── schedule.html
│   ├── slot.html
│   ├── slot_program.html
│   ├── journal.html
│   ├── clients.html
│   ├── clients_create.html
│   ├── clients_edit.html
│   └── subscriptions.html
├── static/
│   └── style.css
├── tests/                  # pytest тесты
│   ├── conftest.py
│   ├── test_bookings.py
│   ├── test_calendar.py
│   ├── test_clients.py
│   ├── test_journal.py
│   ├── test_program.py
│   ├── test_slots.py
│   └── test_subscriptions.py
├── requirements.txt
└── README.md
```

## Стилизация

Основной CSS — `static/style.css`. Переменные `:root` для быстрой настройки темы (цвета, радиусы, отступы). При разработке браузер может кэшировать CSS; используйте DevTools → Disable cache.
