# Тестирование Superior CRM

**189 тестов: 166 unit + 23 E2E**

## Запуск

```powershell
# Все unit-тесты
pytest --ignore=tests/test_e2e.py -q

# Конкретный файл
pytest tests/test_auth.py -v

# E2E-тесты (автостарт сервера с временной БД)
pytest tests/test_e2e.py -v

# E2E с видимым браузером
pytest tests/test_e2e.py --headed
```

## Структура тестов

### Unit-тесты (166)

| Файл | Тестов | Что проверяет |
|------|--------|--------------|
| `test_auth.py` | 8 | Логин, регистрация, logout всех ролей |
| `test_bookings.py` | 5 | capacity, дубликаты, constraint, очистка notes |
| `test_calendar.py` | 3 | Отображение недели, week_offset |
| `test_clients.py` | 7 | CRUD, пагинация, антропометрия, профиль |
| `test_edge_cases.py` | 35 | XSS, SQLi, mass assignment, дашборд |
| `test_exercises.py` | 4 | API групп, упражнений, лог |
| `test_flash.py` | 9 | Flash-модалка |
| `test_journal.py` | 2 | Завершение, журнал |
| `test_logging.py` | 6 | audit-логи |
| `test_optimization.py` | 9 | Тайминги загрузки страниц |
| `test_program.py` | 1 | Сохранение заметки |
| `test_security.py` | 10 | XSS, CSRF, rate limit, CSP |
| `test_session.py` | 5 | Сессии |
| `test_signup.py` | 11 | GET/POST /signup, контакты |
| `test_slots.py` | 4 | Конфликты, прошлое |
| `test_sql.py` | 8 | SQL-консоль |
| `test_strength.py` | 15 | 1ПМ, нормативы, лог, профиль |
| `test_subscriptions.py` | 5 | Абонементы (группировка, списание FIFO) |
| `test_time_slots.py` | 7 | Привязка к time_slot, бронь по слотам, профиль |

### E2E-тесты (23)

| Класс | Роль | Тесты |
|-------|------|-------|
| TestAnonymous | аноним | home, redirects (clients, journal, profile) |
| TestClient | клиент | profile, redirects |
| TestTrainer | тренер | clients, journal, subscriptions, create_client |
| TestAdmin | админ | create_client, logout |
| TestFlash | — | auto_hide, close |
| TestProgram | админ | full_flow (создать → записать → программа → завершить → журнал) |
| TestSignup | аноним | form_visible, success, minimal, nav_link, nav_hidden |
| TestProfile | клиент/админ | client_profile_shows_info, admin_profile_shows_stats |

## Как это работает

### Unit-тесты

- `conftest.py` создаёт временную SQLite БД на каждую сессию тестов
- `CSRF_DISABLE=1` — CSRF middleware отключён
- Фикстура `client` — TestClient, авторизованный как admin
- Фикстура `db_session` — свежая сессия на каждый тест
- `set_session_engine(engine)` — сессии тоже идут в тестовую БД

### E2E-тесты

- `app_url` фикстура запускает uvicorn на свободном порту
- Используется **временная БД** (не `superior.db`), удаляется после тестов
- `CSRF_DISABLE=1` передаётся в окружение подпроцесса
- Playwright браузер управляется через Page-фикстуры

## Известные проблемы

- `test_full_flow` в E2E: слот может не создаться, если `datetime.now() + сдвиг` попадает вне сетки календаря 08-22. Исправлено: время форсируется на 10:00 следующего дня.
- SQLite не поддерживает `FOR UPDATE` полноценно — `with_for_update()` является no-op.
- Тесты с session-scoped engine могут интерферировать через данные — для изоляции используются function-scoped `db_session`.

## Добавление нового теста

```python
# tests/test_my_feature.py
def test_my_route(client, db_session):
    from app.models import MyModel
    # создаём данные через db_session
    obj = MyModel(...)
    db_session.add(obj)
    db_session.commit()
    # делаем запрос через клиент
    r = client.get("/my-route")
    assert r.status_code == 200
    assert "что-то" in r.text
```
