# SUPERIOR CRM

CRM для студии персонального тренинга SUPERIOR. Серверная часть — FastAPI + SQLAlchemy, шаблоны — Jinja2.

## Технологии

- **Python 3.13**, **FastAPI**
- **SQLAlchemy** (синхронный ORM)
- **SQLite** (по умолчанию) / **PostgreSQL** (через `DATABASE_URL`)
- **Alembic** — миграции схемы БД
- **Pydantic v2** — валидация форм
- **Playwright** — E2E-тесты
- **ruff** — линтинг (line-length=120)
- **Chart.js** — графики на дашборде
- **pytest** — 189 тестов (166 unit + 23 E2E)
- **GitHub Actions** — CI (lint + test + migrations)

## Быстрый запуск (SQLite)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m alembic upgrade head
uvicorn main:app --reload
```

Открыть: http://127.0.0.1:8000/

### Учётные записи по умолчанию

| Роль | Логин | Пароль |
|------|-------|--------|
| Администратор | `admin` | `admin` |
| Тренер | `trainer` | `trainer` |
| Клиент | `client_1` | `client_1` |
| Клиент | `client_2` | `client_2` |
| Клиент | `client_3` | `client_3` |

Пароли админа и тренера задаются через переменные окружения `ADMIN_LOGIN`/`ADMIN_PASSWORD`, `TRAINER_LOGIN`/`TRAINER_PASSWORD`.

## Запуск с PostgreSQL

```powershell
$env:DATABASE_URL="postgresql://user:pass@localhost:5432/superior_crm"
python -m alembic upgrade head
uvicorn main:app --reload
```

## Модели данных

| Таблица | Назначение |
|---------|-----------|
| `clients` | Клиенты: ФИО, телефон, `remaining_sessions`, `login`, `password_hash` |
| `slots` | Слоты расписания: время начала, вместимость |
| `bookings` | Бронирования: уникальный ключ `(slot_id, client_id)` |
| `journal` | Журнал проведённых занятий + комментарии (JSON) |
| `training_notes` | Рабочие заметки по клиентам (удаляются при завершении) |
| `sessions` | Сессии пользователей (DB-backed, не cookie) |
| `subscription_purchases` | Покупки абонементов (per-package remaining, FIFO) |
| `training_requests` | Заявки на пробную тренировку |
| `exercise_groups` | Группы упражнений (СПИНА, ГРУДЬ, НОГИ…) |
| `exercises` | Упражнения (53 шт.) |
| `client_exercise_log` | Лог выполнения упражнений (фактические повторы) |
| `training_plan_exercises` | Упражнения в плане тренировки (поаподходно) |

## Функционал

### Аутентификация и роли
- Три роли: **admin**, **trainer**, **client**
- Регистрация новых клиентов (`/register`)
- Вход по логину/паролю (`/login`)
- Профиль с разным наполнением для каждой роли (`/profile`)
- Rate limiting: 5 попыток входа в минуту
- Независимые сессии на разных вкладках (DB-backed session store)

### Клиенты (`/clients`) — admin/trainer только
- Создание, редактирование, удаление клиента
- Фильтрация по имени и телефону
- **Пагинация** (25 на странице)
- Покупка абонемента (1/4/8/12 занятий, 3 time_slot × 3 формата)
- Per-package остаток (`SubscriptionPurchase.remaining`)
- Блокировка записи при отсутствии пакета для time_slot слота

### Расписание (`/schedule`) — все авторизованные
- Недельный календарь 08:00–22:00
- Навигация по неделям (`week_offset`)
- Создание одиночного / массового слота (по интервалу) — admin/trainer
- Массовое удаление слотов по интервалу — admin/trainer
- Защита от пересечения слотов
- Запрет создания слота в прошлом

### Слот (`/slot/{id}`) — все авторизованные (клиенты — read-only)
- Просмотр клиентов в слоте
- Добавление / удаление клиента — admin/trainer
- Проверка вместимости + `select_for_update` (защита от гонок)
- `UNIQUE (slot_id, client_id)` — защита дубликатов на уровне БД

### Программа тренировки (`/slot/{id}/program`) — admin/trainer только
- Список клиентов с переключением по клику
- Редактирование заметки для каждого клиента
- **Автосохранение** — 300ms debounce + sendBeacon
- **Конструктор тренировки** — выбор группы мышц → упражнение → вес/повторы/подходы
- **Таблица упражнений** — каждый подход отдельной строкой, редактируемый столбец «Факт»
- **Перенос из таблицы** — кнопка «Перенести из таблицы» формирует описание с фактическими повторами
- **Прогрессия +5%** — автозаполнение веса/повторов из истории
- Подтверждение занятия → фактические повторы в `ClientExerciseLog`, списание `remaining_sessions`

### Журнал (`/journal`) — admin/trainer только
- Список проведённых занятий с комментариями
- Переносы строк в комментариях сохраняются

### Абонементы (`/subscriptions`) — публичная страница
- Матрица цен: 3 временных слота (утро/день/вечер) × 3 формата (VIP/Double/Group) × 4 пакета (1/4/8/12)
- Покупка абонемента через карточку клиента — admin/trainer

### Личный кабинет (`/profile`)
- Для клиента: телефон, антропометрия (рост/вес/%жира)
- **Остаток по пакетам** — бейджи `Формат Время: осталось/забронировано`
- **Силовые показатели** — 1ПМ для 5 базовых упражнений (формула Эпли)
- **Нормативы (разряды)** — МСМК / МС / КМС / 1-3 разряд с таблицей весов
- **История тренировок** — запланированные и проведённые занятия с планом упражнений
- Для admin/trainer: статистика (клиенты, слоты, журнал)

### SQL-консоль (`/sql`) — admin только
- Выполнение произвольных SQL-запросов (SELECT, DELETE, INSERT, UPDATE)
- Отображение результатов в таблице
- Заметки с частыми запросами (localStorage)

### Публичные страницы
- `/signup` — заявка на пробную тренировку
- `/subscriptions` — абонементы и цены
- `/contacts` — адрес, телефон, соцсети, режим работы

### Конструктор тренировки
- 7 групп мышц: СПИНА, ГРУДЬ, НОГИ, ПЛЕЧИ, БИЦЕПС, ТРИЦЕПС, ПРЕСС
- 53 упражнения
- Автозаполнение с прогрессией +5% из истории клиента
- Каждый подход — отдельная запись с возможностью указать фактические повторы
### Дашборд (`/dashboard`) — admin/trainer
- Выручка по месяцам/дням/часам (Chart.js bar chart) с переключателем агрегации
- Выручка по временным слотам и форматам (pie charts)
- Количество активных клиентов и тренировок за месяц
- Таблица последних 10 продаж

### Бюджет (`/budget`) — admin
- Финансовая статистика: общая и месячная выручка
- История покупок с привязкой к клиенту
## Безопасность

- **CSRF-защита** — `CsrfMiddleware` проверяет токен во всех POST-формах
- **Хеширование паролей** — PBKDF2-SHA256 с уникальной солью (600k итераций)
- **Rate limiting** — 5 попыток в минуту на логин
- **Заголовки безопасности** — CSP, X-Frame-Options: DENY, X-Content-Type-Options: nosniff
- **Валидация форм** — Pydantic (422 при невалидных данных)
- **Row-level lock** — `select_for_update` при бронировании
- **Retry** — до 3 повторов при IntegrityError
- **Аудит** — логирование всех CRUD-операций (create/delete/add)

## Тесты

### Unit-тесты

```powershell
pytest --ignore=tests/test_e2e.py -q   # 166 тестов
```

| Файл | Кол-во | Что проверяет |
|------|--------|--------------|
| `test_auth.py` | 8 | Логин/лог-аут всех ролей, регистрация |
| `test_bookings.py` | 5 | capacity, дубликаты, constraint, очистка notes |
| `test_calendar.py` | 3 | Отображение недели, week_offset |
| `test_clients.py` | 3 | CRUD, пагинация |
| `test_edge_cases.py` | 34 | XSS, SQLi, граничные значения |
| `test_flash.py` | 9 | Flash-модалка, countdown, replaceState |
| `test_journal.py` | 2 | Завершение слота, страница журнала |
| `test_logging.py` | 6 | audit_log, CREATE/DELETE/ADD записи |
| `test_optimization.py` | 9 | Тайминги с большими dataset-ами |
| `test_program.py` | 1 | Save + persist |
| `test_security.py` | 10 | XSS, хеши, CSRF, rate limit, CSP |
| `test_session.py` | 5 | Независимость сессий, logout |
| `test_slots.py` | 4 | Конфликты, прошлое |
| `test_subscriptions.py` | 3 | Абонементы, лимиты |

### E2E-тесты (Playwright)

```powershell
pytest tests/test_e2e.py -v  # 23 теста (автостарт сервера)
pytest tests/test_e2e.py --headed  # с видимым браузером
```

Автоматически запускают uvicorn на свободном порту с `CSRF_DISABLE=1` и временной БД (не затрагивает `superior.db`).

| Класс | Роль | Тесты |
|-------|------|-------|
| `TestAnonymous` | Неавторизованный | home, редиректы на login |
| `TestClient` | Клиент | profile, редиректы на / |
| `TestTrainer` | Тренер | clients, journal, subscriptions, create_client |
| `TestAdmin` | Админ | create_client, logout |
| `TestFlash` | Любой | auto-hide, manual close |

### Линтинг

```powershell
ruff check .
```

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
├── main.py                  # Точка входа (FastAPI app + middleware + seed)
├── app/
│   ├── models.py            # SQLAlchemy модели (6 таблиц)
│   ├── database.py          # Engine, Session, get_db, Jinja2 templates
│   ├── schemas.py           # Pydantic-схемы (данные + формы)
│   ├── forms.py             # Depends-функции Form → Pydantic
│   ├── auth.py              # Аутентификация, роли, require_role()
│   ├── csrf.py              # CSRF-мидлварь и генератор токенов
│   ├── session.py           # DB-backed сессии (независимые вкладки)
│   ├── ratelimit.py         # Rate limiter (in-memory)
│   ├── logging_config.py    # Настройка логирования
│   ├── timezone.py          # Утилиты времени (UTC storage, localtime display)
│   └── routes/
│       ├── clients.py       # /clients
│       ├── schedule.py      # /schedule, /slot/{id}
│       ├── slots.py         # /slots/*, /slot/{id}/add|remove|complete
│       ├── program.py       # /slot/{id}/program
│       └── journal.py       # /, /journal, /subscriptions
├── templates/               # Jinja2 шаблоны (11 файлов)
├── static/style.css
├── tests/                   # 15 файлов, 129 тестов
├── alembic/                 # Миграции (3 версии)
├── .github/workflows/       # CI (GitHub Actions)
├── requirements.txt
└── README.md
```

Основной CSS — `static/style.css`. Переменные `:root` для быстрой настройки темы. Используйте DevTools → Disable cache при разработке.
