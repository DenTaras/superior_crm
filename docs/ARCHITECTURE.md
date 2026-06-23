# Архитектура Superior CRM

## Стек

| Компонент | Технология |
|-----------|-----------|
| Фреймворк | FastAPI (синхронные маршруты) |
| ORM | SQLAlchemy (синхронный) |
| Шаблоны | Jinja2 |
| БД | SQLite (dev) / PostgreSQL (prod) |
| Миграции | Alembic (5 версий) + runtime-миграции |
| Валидация форм | Pydantic v2 |
| E2E-тесты | Playwright (pytest-playwright) |
| Линтер | ruff (line-length=120) |

## Структура директорий

```
superior_crm/
├── app/
│   ├── __init__.py          # (пустой)
│   ├── models.py            # SQLAlchemy модели (19 таблиц)
│   ├── database.py          # Engine, SessionLocal, get_db, templates, миграции
│   ├── schemas.py           # Pydantic-схемы форм
│   ├── forms.py             # Парсеры форм из POST-данных
│   ├── auth.py              # Аутентификация, роли, профиль
│   ├── session.py           # DbSessionMiddleware (сессии в БД)
│   ├── csrf.py              # Stateless CSRF (HMAC-SHA256)
│   ├── pricing.py           # Матрица цен, helpers (time_slot, format)
│   ├── strength.py          # 1ПМ (Эпли), нормативы
│   ├── nutrition.py         # Расчёт BMR/TDEE/макросов, генерация плана
│   ├── nutrition2.py        # Нормализованные продукты, список покупок
│   ├── seed_exercises.py    # 7 групп, 53 упражнения
│   ├── seed_products.py     # Seed 93 продуктов, ~300 связей MealProduct
│   ├── seed_meals.py        # Seed 62 шаблонов блюд
│   ├── timezone.py          # now(), now_aware()
│   ├── logging_config.py    # audit_log, request-логгер
│   ├── ratelimit.py         # In-memory rate limiter
│   └── routes/
│       ├── clients.py       # /clients — CRUD + подписки
│       ├── schedule.py      # /schedule — календарь
│       ├── slots.py         # /slots/* — слоты, брони, завершение
│       ├── program.py       # /slot/{id}/program — план тренировки
│       ├── journal.py       # /journal — журнал
│       ├── signup.py        # /signup — публичная заявка
│       ├── sql_console.py   # /sql — консоль (admin)
│       ├── exercises_api.py # /api/exercise-* — AJAX для конструктора
│       ├── budget.py        # /budget — финансы с расходами (admin)
│       ├── dashboard.py     # /dashboard — дашборд с графиками (admin/trainer)
│       └── employees.py     # /employees — CRUD сотрудников (admin)
├── templates/               # Jinja2-шаблоны (16 шт.)
│   ├── base.html            # Базовый layout
│   ├── employees.html       # Список сотрудников
│   ├── employee_form.html   # Создание/редактирование сотрудника
│   ├── privacy.html         # Политика конфиденциальности
│   ├── nutrition.html       # Питание v1
│   ├── nutrition2.html      # Питание v2 / список покупок
│   └── ...
├── static/
│   └── style.css            # BEM CSS (тёмная тема)
├── tests/                   # 205 unit + 3 skipped
├── docs/                    # Документация (5 файлов)
├── alembic/                 # 5 миграций
├── main.py                  # Точка входа, middleware, seed
├── requirements.txt
└── pyproject.toml
```

## Middleware Chain (порядок обработки запроса)

```
1. DbSessionMiddleware — подставляет request.session (DB-backed)
2. CSRFCheck — проверяет HMAC-токен на POST/PUT/DELETE
3. add_security_headers — CSP, X-Frame-Options, X-Content-Type-Options
4. RequestLogger — логирует метод, путь, статус, длительность
5. Маршрутизация FastAPI → зависимость require_role → обработчик
```

## Dependency Injection

- `get_db` — возвращает SQLAlchemy-сессию
- `require_role("admin", "trainer")` — проверяет роль, при неудаче редирект на /login
- `get_current_user` — возвращает `request.session.get('user')` или None
- `parse_*_form` — парсит POST-данные в Pydantic-схему

## Аутентификация

- Admin/trainer — по логину/паролю из переменных окружения (ADMIN_LOGIN/PASSWORD, TRAINER_LOGIN/PASSWORD)
- Сотрудники (Employee) — по логину/паролю из таблицы employees (PBKDF2-SHA256), роль определяется по должности
- Client — по логину/паролю из таблицы clients (PBKDF2-SHA256)
- Сессии — в таблице sessions (DB-backed, не cookie)
- Rate limit — 5 попыток в минуту на логин (in-memory)
