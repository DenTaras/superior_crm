# TODO — Superior CRM

> Актуальное состояние на 16.06.2026.
> ✅ = выполнено, 🔄 = в работе, ◻ = не начато.

---

## ✅ Выполнено

### Инфраструктура
- **Рефакторинг** — `app/` пакет: `models`, `database`, `schemas`, `forms`, `routes/`, точка входа `main.py`
- **Alembic** — миграции, `env.py` читает `DATABASE_URL`
- **PostgreSQL** — поддержка через `DATABASE_URL`, fallback при отсутствии драйвера
- **CI/CD** — GitHub Actions: `pytest` (84), `ruff`, `alembic upgrade head`
- **Логирование** — request-логгер (middleware), audit-лог (`CREATE/UPDATE/DELETE/COMPLETE`), трассировка (`TRACE=1`)
- **pyproject.toml** — конфиг ruff, pytest, маркеры

### База данных
- **UNIQUE constraint** `(slot_id, client_id)` — модель + миграция + тест
- **Race conditions** — `select_for_update` + retry при `IntegrityError`

### Валидация
- **Pydantic-формы** — `ClientCreateForm`, `SlotAddForm`, `BookingAddForm` и др.
- **422 вместо 500** для невалидных данных

### Функционал
- **Абонементы** — пакеты 4/8/12, списание при завершении, блокировка при 0
- **Программа тренировки** — автосохранение (sendBeacon + debounce), data-атрибуты вместо Jinja2 в JS
- **Журнал** — перенос строк в комментариях
- **Пагинация** клиентов (25 на странице)
- **Трассировка запросов** — `TRACE=1` для детального лога (headers, body, timing)

### Тесты — 84 шт.
| Файл | Тестов | Что проверяет |
|------|--------|--------------|
| `test_bookings` | 5 | capacity, дубликаты, DB constraint, очистка notes |
| `test_calendar` | 3 | отображение недели, week_offset |
| `test_clients` | 3 | CRUD, пагинация |
| `test_edge_cases` | 34 | XSS, SQLi, mass assignment, граничные значения |
| `test_journal` | 2 | завершение слота, декремент |
| `test_logging` | 6 | audit-логи (CREATE, DELETE, ADD, SUBSCRIPTION) |
| `test_optimization` | 10 | тайминги (150 слотов, 100 записей, bulk) |
| `test_program` | 1 | save + persist, HTML-level проверка |
| `test_slots` | 3 | конфликты, прошлое |
| `test_subscriptions` | 3 | абонементы, лимиты |
| E2E (`test_e2e`) | 8 | Playwright: навигация, создание клиента/слота |

### Прочее
- `.gitignore` — `*.db`, `__pycache__`, `.ruff_cache`, `.pytest_cache`, IDE
- `main.py` — абсолютные пути к `static/` и `templates/`
- 0 предупреждений в тестах

---

## ◻ P2 — Средний приоритет

- **Аутентификация** — базовая auth (+ роли)
- **Таймзоны** — хранить даты в UTC, конвертировать при рендеринге
- **Flash-уведомления** — автоскрытие через JS, детали конфликта
- **requirements pinning** — зафиксировать версии зависимостей

---

## ◻ P3 — Низкий / Опционально

- **Keyboard navigation** для календаря (стрелки, Enter)
- **Улучшить UX** модальных окон (анимация, понятные сообщения)
- **Production-конфигурация** — CORS, middleware, метрики
- **Иконки / цветовая система** для статусов тренировок
- **Деплой** — Dockerfile, docker-compose (app + postgres)

---

## Заметки

- `ensure_client_columns()` / `ensure_journal_columns()` — runtime-миграции; при переходе на чистый PG можно удалить