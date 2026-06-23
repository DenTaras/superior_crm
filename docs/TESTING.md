# Тестирование Superior CRM

**205 тестов + 3 skipped**

## Запуск

```powershell
# Все unit-тесты
pytest -q

# Конкретный файл
pytest tests/test_auth.py -v

# С отчётом по времени
pytest -q --durations=5
```

## Структура тестов

### Полный список

| Файл | Тестов | Что проверяет |
|------|--------|--------------|
| `test_auth.py` | 8 | Логин, регистрация, logout всех ролей |
| `test_bookings.py` | 5 | capacity, дубликаты, constraint, очистка notes |
| `test_calendar.py` | 3 | Отображение недели, week_offset |
| `test_clients.py` | 7 | CRUD, пагинация, антропометрия, профиль |
| `test_edge_cases.py` | 35 | XSS, SQLi, mass assignment, дашборд |
| `test_employees.py` | 10 | Сотрудники, назначение тренеров, бюджет/расходы |
| `test_exercises.py` | 4 | API групп, упражнений, лог |
| `test_flash.py` | 9 | Flash-модалка |
| `test_full_integration.py` | 3 | Полный цикл + budget + consumption log |
| `test_journal.py` | 2 | Завершение, журнал |
| `test_logging.py` | 6 | audit-логи |
| `test_nutrition.py` | 17 | BMR/TDEE, макросы, план, UI, настройки |
| `test_nutrition2.py` | 9 | Список покупок, .txt, seed, дубликаты |
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
