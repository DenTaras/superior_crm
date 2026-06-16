"""Настройка логирования и audit-логгер для CRUD-операций."""

import logging
import sys
from datetime import datetime


def setup_logging():
    """Настроить корневой логгер: stdout + формат.

    Если установлена переменная TRACE=1, логгеры superior.trace
    будут писать на уровне DEBUG.
    """
    import os as _os

    level = logging.DEBUG if _os.getenv("TRACE") else logging.INFO
    logger = logging.getLogger("superior")
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)

    if not logger.handlers:
        logger.addHandler(handler)

    return logger


# Создаём логгер при импорте
logger = setup_logging()


def audit_log(logger_name: str, action: str, **details):
    """Записать audit-событие в лог.

    Параметры:
        logger_name — имя логгера (например, 'superior.audit.clients')
        action     — действие (CREATE, UPDATE, DELETE, COMPLETE, ...)
        details    — пары ключ=значение с деталями (client_id, slot_id, ...)
    """
    log = logging.getLogger(logger_name)
    parts = [f"[{action}]"]
    for k, v in details.items():
        parts.append(f"{k}={v}")
    log.info(" ".join(parts))
