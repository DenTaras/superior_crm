# SUPERIOR CRM

Минимальная CRM для студии персонального тренинга SUPERIOR. Проект — учебный пример с серверной частью на FastAPI и шаблонами Jinja2.

Технологии
- Python, FastAPI
- SQLAlchemy (синхронный)
- SQLite (`superior.db`) для локальной разработки
- Jinja2 templates, статический CSS в `static/style.css`
- Запуск: `uvicorn app:app --reload`

Что реализовано
- Модели: `Client`, `Slot`, `Booking`.
- CRUD для клиентов: `/clients`, `/clients/add`, `/clients/edit/{id}`, `/clients/delete/{id}`.
- CRUD для слотов: `/slots`, `/slots/add`, `/slots/edit/{id}`, `/slots/delete/{id}`.
- Просмотр расписания (неделя): `GET /` (`templates/schedule.html`).
- Страница слота с записью/удалением клиента: `GET /slot/{id}`, `POST /slot/{id}/add`, `POST /slot/{id}/remove`.

Особенности и текущие решения
- Для простоты используется SQLite; в локальной разработке присутствует небольшая runtime-логика для добавления новых колонок в `clients`, если модель расширялась — это удобство, но не замена миграциям.
- Введены Pydantic-схемы и зависимость `get_db` для упрощения обработки запросов (см. `app.py`).
- В UI CSS рефакторинг: добавлена утилитарная система (`.panel`, `.btn`, `.btn--small`, `.field`, `.form-row` и т.д.) для удобства поддержки.

Стили и кэш
- Основная стилизация в `static/style.css`. Используйте переменные `:root` для быстрой настройки темы (цвета, радиусы, отступы).
- При разработке браузер может кэшировать CSS; для разработки используйте:
	- DevTools → Disable cache (при открытом DevTools).
	- Быстрое версионирование URL: `<link href="/static/style.css?v=1.2">`.

Ограничения и рекомендации
- Для продакшена: перенести БД на PostgreSQL и настроить миграции через Alembic.
- Добавить транзакционную защиту при бронированиях, ограничения на уровне БД и/или optimistic locking для предотвращения гонок.
- Добавить клиентские маски/валидацию (телефон, дата) и тесты.

Дальше
- При желании могу автоматически привести шаблоны к полному использованию утилит (удалить оставшиеся legacy-классы), подготовить Alembic-миграцию или добавить клиентский input-mask для телефона.

Быстрый запуск
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1   # PowerShell
pip install -r requirements.txt
uvicorn app:app --reload
```

Открыть: http://127.0.0.1:8000/
