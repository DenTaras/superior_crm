"""Утилиты для работы с таймзонами.

По умолчанию сервер работает в UTC, отображение — МСК (UTC+3).
Можно переопределить через переменную окружения TZ.
"""

import os
from datetime import datetime, timezone, timedelta

# Часовой пояс для отображения (по умолчанию МСК = UTC+3)
LOCAL_TZ_OFFSET = int(os.getenv("TZ_OFFSET", "3"))


def now() -> datetime:
    """Текущее время в UTC (naive — совместимо с SQLite-хранением)."""
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
