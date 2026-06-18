# TODO — Superior CRM

> Актуальное состояние на 18.06.2026.
> ✅ = выполнено, 🔄 = в работе, ◻ = не начато.

---

## ✅ Выполнено

### Инфраструктура
- ✅ **Рефакторинг** — `app/` пакет: models, database, schemas, forms, routes/, точка входа `main.py`
- ✅ **Alembic** — миграции, 5 версий (initial, unique constraint, client login, sessions, training_requests)
- ✅ **PostgreSQL** — поддержка через `DATABASE_URL`, fallback при отсутствии драйвера
- ✅ **CI/CD** — GitHub Actions: pytest (123), ruff check, alembic upgrade head
- ✅ **Логирование** — request-логгер, audit-лог (CREATE/UPDATE/DELETE/COMPLETE/ADD), трассировка (TRACE=1)
- ✅ **pyproject.toml** — конфиг ruff, pytest, маркеры

### Аутентификация и безопасность
- ✅ **Роли** — admin / trainer / client через `require_role()`
- ✅ **Регистрация клиентов** — `/register`
- ✅ **Сессии в БД** — независимые вкладки (не cookie-only)
- ✅ **CSRF-защита** — stateless HMAC-подпись (без `request.session`)
- ✅ **Хеширование паролей** — PBKDF2-SHA256 с уникальной солью
- ✅ **Rate limiting** — 5 попыток в минуту на логин
- ✅ **Заголовки безопасности** — CSP, X-Frame-Options, X-Content-Type-Options

### База данных
- ✅ **UNIQUE constraint** `(slot_id, client_id)` — модель + миграция + тест
- ✅ **Race conditions** — select_for_update + retry при IntegrityError

### Валидация
- ✅ **Pydantic-формы** — ClientCreateForm, SlotAddForm, BookingAddForm и др.
- ✅ **422 вместо 500** для невалидных данных

### Функционал
- ✅ **Абонементы** — пакеты 4/8/12, списание при завершении, блокировка при 0
- ✅ **Программа тренировки** — автосохранение (sendBeacon + debounce)
- ✅ **Журнал** — перенос строк в комментариях
- ✅ **Пагинация** клиентов (25 на странице)
- ✅ **Трассировка запросов** — TRACE=1 (headers, body, timing)
- ✅ **Flash-уведомления** — автоскрытие через JS
- ✅ **Таймзоны** — UTC storage, localtime display (TZ_OFFSET)
- ✅ **requirements.txt** — зафиксированы версии
- ✅ **Запись на тренировку** — `/signup` (форма + заявка в БД + страница успеха)
- ✅ **Stateless CSRF** — HMAC-SHA256 подпись токена (без `request.session`)
- ✅ **Middleware-порядок** — отлажен и задокументирован

### Тесты — 123 unit + 21 E2E = 144
| Файл | Тестов | Что проверяет |
|------|--------|--------------|
| `test_auth` | 8 | Логин всех ролей, регистрация, logout |
| `test_bookings` | 5 | capacity, дубликаты, constraint, очистка notes |
| `test_calendar` | 3 | Отображение недели, week_offset |
| `test_clients` | 3 | CRUD, пагинация |
| `test_edge_cases` | 34 | XSS, SQLi, mass assignment, границы |
| `test_flash` | 9 | Flash-модалка, countdown, replaceState |
| `test_journal` | 2 | Завершение слота, журнал |
| `test_logging` | 6 | audit-логи |
| `test_optimization` | 9 | Тайминги с большими dataset-ами |
| `test_program` | 1 | Save + persist |
| `test_security` | 10 | XSS, хеши, CSRF, rate limit, CSP |
| `test_session` | 5 | Независимость сессий |
| `test_signup` | 9 | GET/POST /signup, валидация, БД |
| `test_slots` | 4 | Конфликты, прошлое |
| `test_subscriptions` | 3 | Абонементы, лимиты |
| E2E (`test_e2e`) | 21 | Все роли + signup |

### Прочее
- `.gitignore` — *.db, __pycache__, .ruff_cache, .pytest_cache, IDE
- `superior.db` исключён из git

---

## 🔄 P1 — Высокий приоритет

### 1. Дашборд / Статистика (`/dashboard`)
Главная страница для админа/тренера с метриками:
- Кол-во активных клиентов, занятий за неделю/месяц
- Ближайшие слоты, клиенты с 0 оставшихся занятий
- График посещаемости (Canvas или SVG)

### 2. Онлайн-запись на конкретный слот
Замена (или дополнение) простой заявки: клиент сам выбирает свободный слот из расписания и бронирует. Нужна:
- Страница со свободными слотами (фильтр по дате)
- Подтверждение брони без регистрации (или через быструю регистрацию)

### 3. История покупок и списаний (`subscription_log`)
Новая таблица для аудита операций с абонементами:
- Дата, клиент, тип (покупка/списание), кол-во занятий, кто провёл
- Отображение истории в карточке клиента

---

## 🔄 P2 — Средний приоритет

### 4. Расширенный профиль клиента (`/clients/{id}`)
Страница с историей: посещённые тренировки (из журнала), прогресс (веса, подходы), оставшиеся занятия.

### 5. Экспорт в CSV / PDF
Кнопки «Выгрузить журнал», «Выгрузить клиентов» для admin/trainer.

### 6. Повторяющиеся слоты
Создание регулярного расписания: «каждый ПН/СР/ПТ в 10:00 на N недель».

---

## ◻ P3 — Низкий / Опционально

- **Уведомления** — Email/SMS напоминания о тренировках
- **Онлайн-оплата** — интеграция с платежным шлюзом
- **Комментарии к клиентам** — заметки на карточке клиента
- **Keyboard navigation** для календаря (стрелки, Enter)
- **Production-конфигурация** — CORS, метрики, healthcheck
- **Деплой** — Dockerfile, docker-compose (app + postgres)
- **WebSocket** — real-time обновления расписания
- **API-документация** — OpenAPI/Swagger

---

## Заметки

- `run_startup_migrations()` в `database.py` — runtime-миграции для совместимости SQLite/PG; при переходе на чистый PG можно удалить
- E2E-тесты автостартуют uvicorn на свободном порту
- CSRF отключён в тестовом окружении (CSRF_DISABLE=1)