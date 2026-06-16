"""Простой in-memory rate limiter (на базе словаря)."""

import time
import threading
from typing import Dict, Tuple

_lock = threading.Lock()
_store: Dict[str, list] = {}
"""key → [timestamp, ...]"""


def check_rate_limit(key: str, max_attempts: int = 5, window_sec: int = 60) -> Tuple[bool, int]:
    """Проверить, не превышен ли лимит попыток для ключа.

    Args:
        key: идентификатор (IP или логин)
        max_attempts: максимум попыток в окне
        window_sec: окно в секундах

    Returns:
        (разрешено, сколько осталось попыток)
    """
    now = time.time()
    with _lock:
        timestamps = _store.get(key, [])
        # отсекаем старые записи
        timestamps = [t for t in timestamps if now - t < window_sec]
        if len(timestamps) >= max_attempts:
            _store[key] = timestamps
            remaining = 0
            return False, remaining
        timestamps.append(now)
        _store[key] = timestamps
        remaining = max_attempts - len(timestamps)
        return True, remaining


def clear_rate_limit(key: str) -> None:
    """Сбросить счётчик попыток (после успешного входа)."""
    with _lock:
        _store.pop(key, None)
