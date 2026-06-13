SKILL — Разворачивание и полезные команды
=========================================

Короткая инструкция разработчику для локальной настройки, запуска и основных операций.

1) Требования
- Python 3.10+ (или совместимая 3.x). 
- Рекомендуется создать виртуальное окружение.

2) Быстрая настройка (Windows PowerShell)

```powershell
# в корне проекта
python -m venv .venv
# активировать (PowerShell)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
# установить зависимости
pip install -r requirements.txt
# проверить синтаксис
python -m py_compile app.py
# запустить сервер (uvicorn должен быть в requirements)
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Unix / macOS (bash/zsh)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m py_compile app.py
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

3) Работа с базой данных
- По умолчанию приложение использует SQLite `superior.db` в корне.
- На локальной разработке скрипт `ensure_client_columns()` добавляет колонки (dev convenience).
- Для production: использовать Alembic и Postgres (см. раздел «Миграции» ниже).

4) Миграции (рекомендация)
- Инициализация Alembic (один раз):

```bash
pip install alembic
alembic init alembic
# настроить alembic.ini и env.py для SQLAlchemy engine
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

5) Полезные команды разработки
- Проверка статики/шаблонов: открыть `/schedule`, `/clients` в браузере.
- Быстрая синтаксическая проверка проекта:

```bash
python -m py_compile app.py
```

- Форматирование/линтинг (рекомендация):

```bash
pip install black flake8
black .
flake8 .
```

6) Тесты
- Установите dev‑зависимости:

```bash
pip install -r requirements-dev.txt
```

- Запустить тесты вручную:

```bash
pytest
```

- Автозапуск тестов при изменениях (рекомендуется установить `pytest-watch`):

```bash
ptw
# или
bash scripts/watch-tests.sh
```

6) Тесты / CI
- В репозитории тестов нет — рекомендую добавить `pytest` и пару интеграционных тестов (CRUD клиентов, создание слота, конфликт слота).
- Для CI (GitHub Actions): запуск `pip install -r requirements.txt`, `python -m py_compile app.py`, `pytest` и `flake8`.

7) Рекомендации по безопасности и продакшн
- Переключиться на PostgreSQL для продакшна и использовать Alembic для миграций.
- Защитить CRUD маршруты (аутентификация/роли) при открытии в сеть.
- Для слотов использовать DB constraints/EXCLUDE (Postgres) или транзакции, чтобы избежать race conditions.

8) Быстрые заметки по разработке
- Навигация в календаре использует `week_offset` в query params — сохраняйте его в формах/ссылках.
- Формы слотов отправляют POST на `/slots/add` и `/slots/edit/{id}`; редиректы возвращают на `/schedule`.
 - Пишите русскоязычные докстринги/комментарии для всех новых функций и фикстур (включая тесты). Это помогает поддерживать код понятным для команды.

9) Если хотите, могу:
- добавить `scripts/setup.sh` и `scripts/run.sh` (или Makefile) для автоматизации,
- настроить Alembic и примерную миграцию,
- создать базовые pytest тесты для слотов/бронирований.

---
Файл сгенерирован агентом — при необходимости адаптирую под ваши предпочтения (PowerShell vs bash, дополнительные переменные окружения и т.п.).