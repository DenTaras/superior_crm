# TODO — Superior CRM

> Актуальное состояние на 16.06.2026.
> ✅ = выполнено, 🔄 = в работе, ◻ = не начато.

---

## ✅ Выполнено

### Инфраструктура
- **Alembic** — миграции настроены, `env.py` читает `DATABASE_URL`.
- **PostgreSQL** — поддержка через `DATABASE_URL`, Inspector вместо PRAGMA.
- **Рефакторинг** — `app.py` разбит на `models.py`, `database.py`, `schemas.py`, `routes/`, `forms.py`.
- **CI/CD** — GitHub Actions: `pytest` (78), `ruff`, `alembic upgrade head`.
- **pyproject.toml** — конфиг ruff и pytest.

### База данных
- **UNIQUE constraint** `(slot_id, client_id)` на `bookings` — модель + миграция + тест.
- **Race conditions** — `select_for_update` в бронировании, retry при `IntegrityError`.

### Валидация
- **Pydantic-формы** — `ClientCreateForm`, `SlotAddForm`, `BookingAddForm` и др. с `ge`/`le`/`min_length`/`field_validator`.
- **422 вместо 500** для невалидных данных форм.

### Функционал
- **Абонементы** — пакеты 4/8/12, списание при завершении, блокировка при 0.
- **Программа тренировки** — автосохранение (sendBeacon + debounce), data-атрибуты вместо Jinja2 в JS.
- **Журнал** — перенос строк в комментариях.
- **Пагинация** клиентов (25 на странице).

### Тесты — 78 шт.
- `test_bookings` — capacity, дубликаты, DB-level constraint, удаление слота
- `test_calendar` — отображение недели, week_offset
- `test_clients` — CRUD, пагинация
- `test_edge_cases` — XSS, SQLi, mass assignment, граничные значения
- `test_journal` — создание записи при завершении, декремент
- `test_optimization` — тайминги (150 слотов, 100 клиентов, bulk)
- `test_program` — save + persist, HTML-level проверка
- `test_slots` — конфликты, прошлое
- `test_subscriptions` — страница абонементов, добавление, лимиты

---

## ◻ P2 — Средний приоритет

- **Аутентификация** — базовая auth (+ роли), если приложение будет доступно извне.
- **Таймзоны** — хранить даты в UTC, конвертировать при рендеринге.
- **Flash-уведомления** — автоскрытие через JS, показывать детали конфликта (время/ID).
- **Логирование** — audit log для CRUD-операций.
- **requirements pinning** — зафиксировать версии зависимостей.

---

## ◻ P3 — Низкий / Опционально

- **Keyboard navigation** для календаря (стрелки, Enter).
- **Улучшить UX** модальных окон (анимация, понятные сообщения).
- **Production-конфигурация** — CORS, middleware, метрики.
- **Иконки / цветовая система** для статусов тренировок.
- **Деплой** — Dockerfile, docker-compose (app + postgres).
- **E2E-тесты** через Playwright.

---

## Заметки

- Проверка пересечения слотов — на уровне приложения с `select_for_update` + retry.
- Для продакшна: Postgres + транзакции.
- `ensure_client_columns()` / `ensure_journal_columns()` — runtime-миграции для локальной разработки; при переходе на чистый PG их можно удалить.