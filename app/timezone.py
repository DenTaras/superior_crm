"""Утилиты для работы с таймзонами.

Все времена в БД хранятся как локальные (наивные, без timezone),
потому что браузер отправляет их из datetime-local в локальном времени.
Поэтому `now()` возвращает локальное время (Омск UTC+6 по умолчанию).

Можно переопределить через переменную окружения TZ_OFFSET.
"""

import os
from datetime import datetime, timezone, timedelta

# Часовой пояс (по умолчанию Омск = UTC+6)
LOCAL_TZ_OFFSET = int(os.getenv("TZ_OFFSET", "6"))


def now() -> datetime:
    """Текущее локальное время (naive) — подходит для сравнения с временами в БД.

    Все слоты в БД хранятся в локальном времени (браузер присылает
    datetime-local без таймзоны), поэтому сравнения корректны только
    если tz_now() тоже возвращает локальное время.
    """
    utc = datetime.now(timezone.utc)
    local = utc.astimezone(timezone(timedelta(hours=LOCAL_TZ_OFFSET)))
    return local.replace(tzinfo=None)


def now_utc() -> datetime:
    """Текущее время в UTC (naive)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def now_aware() -> datetime:
    """Текущее время в UTC (aware)."""
    return datetime.now(timezone.utc)


def localtime(dt: datetime | None) -> datetime | None:
    """Конвертировать наивное или UTC-время в локальное (смещение TZ_OFFSET)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=LOCAL_TZ_OFFSET)))
