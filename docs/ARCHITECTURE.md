# Архитектура Superior CRM

## Стек

| Компонент | Технология |
|-----------|-----------|
| Фреймворк | FastAPI (синхронные маршруты) |
| ORM | SQLAlchemy (синхронный) |
| Шаблоны | Jinja2 |
| БД | SQLite (dev) / PostgreSQL (prod) |
| Миграции | Alembic |
| Валидация форм | Pydantic v2 |
| E2E-тесты | Playwright (pytest-playwright) |
| Линтер | ruff (line-length=120) |

## Структура директорий

```
superior_crm/
├── app/
│   ├── __init__.py          # (пустой)
│   ├── models.py            # SQLAlchemy модели (12 таблиц)
│   ├── database.py          # Engine, SessionLocal, get_db, templates, миграции
│   ├── schemas.py           # Pydantic-схемы форм
│   ├── forms.py             # Парсеры форм из POST-данных
│   ├── auth.py              # Аутентификация, роли, профиль
│   ├── session.py           # DbSessionMiddleware (сессии в БД)
│   ├── csrf.py              # Stateless CSRF (HMAC-SHA256)
│   ├── pricing.py           # Матрица цен, helpers (time_slot, format)
│   ├── strength.py          # 1ПМ (Эпли), нормативы
│   ├── seed_exercises.py    # 7 групп, 53 упражнения
│   ├── timezone.py          # now(), now_aware()
│   ├── logging_config.py    # audit_log, request-логгер
│   ├── ratelimit.py         # In-memory rate limiter
│   └── routes/
│       ├── clients.py       # /clients — CRUD + подписки
│       ├── schedule.py      # /schedule — календарь
│       ├── slots.py         # /slot/{id}, /slots/* — слоты, брони, завершение
│       ├── program.py       # /slot/{id}/program — план тренировки
│       ├── journal.py       # /journal — журнал
│       ├── signup.py        # /signup — публичная заявка
│       ├── sql_console.py   # /sql — консоль (admin)
│       ├── exercises_api.py # /api/exercise-* — AJAX для конструктора
│       ├── budget.py        # /budget — финансы (admin)
│       └── dashboard.py     # /dashboard — дашборд с графиками (admin/trainer)
├── templates/               # Jinja2-шаблоны (17 шт.)
├── static/
│   └── style.css            # BEM CSS (тёмная тема)
├── tests/                   # 166 unit + 23 E2E = 189 тестов
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
- Client — по логину/паролю из таблицы clients (PBKDF2-SHA256)
- Сессии — в таблице sessions (DB-backed, не cookie)
- Rate limit — 5 попыток в минуту на логин (in-memory)
