"""Сессии на основе БД: данные хранятся в таблице sessions, в cookie — только session_id.

Позволяет независимо работать с разными учётками в разных вкладках браузера.
"""

import json
import secrets
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from sqlalchemy import Column, Integer, String, Text, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

SessionBase = declarative_base()


class DbSessionModel(SessionBase):
    """Модель сессии в БД."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    data = Column(Text, nullable=False, default="{}")


# Engine для сессий — по умолчанию из database.py, можно переопределить
_session_engine = None


def set_session_engine(engine):
    """Переопределить engine для хранения сессий (нужно для тестов)."""
    global _session_engine, _SessionFactory
    _session_engine = engine
    SessionBase.metadata.create_all(engine)
    _SessionFactory = sessionmaker(bind=engine)


def _get_session_factory():
    global _session_engine, _SessionFactory
    if _session_engine is None:
        from app.database import engine as app_engine
        _session_engine = app_engine
        SessionBase.metadata.create_all(_session_engine)
        _SessionFactory = sessionmaker(bind=_session_engine)
    return _SessionFactory

COOKIE_NAME = "sid"
"""Имя cookie с ID сессии."""

COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 дней


class DbSessionMiddleware(BaseHTTPMiddleware):
    """Middleware: хранит данные сессии в БД, в cookie — только session_id.

    Подменяет request.session на dict-подобный объект, который
    автоматически сохраняется в БД при завершении запроса.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        sid = request.cookies.get(COOKIE_NAME)
        data = {}

        if sid:
            data = _load_session(sid)
            if data is None:
                sid = None
                data = {}  # сессия не найдена — чистая сессия

        if sid is None:
            sid = _generate_sid()

        # подсовываем сессию в request
        session_proxy = _SessionProxy(sid, data)
        request.scope["session"] = session_proxy

        response = await call_next(request)

        # сохраняем и обновляем cookie, если были изменения
        if session_proxy._dirty:
            _save_session(session_proxy._sid, session_proxy._data)
            # всегда обновляем cookie (даже если уже есть — вдруг SID сменился)
            response.set_cookie(
                key=COOKIE_NAME,
                value=session_proxy._sid,
                max_age=COOKIE_MAX_AGE,
                httponly=True,
                samesite="lax",
            )

        return response


class _SessionProxy:
    """dict-подобный объект сессии, который отслеживает изменения."""

    def __init__(self, sid: str, data: dict):
        self._sid = sid
        self._data = data
        self._dirty = False

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if self._data.get(key) != value:
            self._data[key] = value
            self._dirty = True

    def __delitem__(self, key: str) -> None:
        if key in self._data:
            del self._data[key]
            self._dirty = True

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def clear(self) -> None:
        if self._data:
            self._data.clear()
            self._dirty = True

    def regenerate_id(self) -> str:
        """Создать новый session_id, скопировав текущие данные.

        Старый session_id остаётся в БД нетронутым — так другая вкладка
        браузера со старым cookie продолжит видеть свою сессию.
        Возвращает новый session_id.
        """
        self._sid = _generate_sid()
        self._dirty = True
        return self._sid

    @property
    def sid(self) -> str:
        return self._sid

    def __repr__(self) -> str:
        return repr(self._data)


def _generate_sid() -> str:
    return secrets.token_hex(32)


def _load_session(sid: str) -> dict | None:
    """Загрузить данные сессии из БД. Вернёт None, если сессии нет."""
    try:
        db = _get_session_factory()()
        row = db.query(DbSessionModel).filter(DbSessionModel.session_id == sid).first()
        if row is None:
            return None
        return json.loads(row.data)
    except Exception as ex:
        print(f"[WARN] _load_session({sid!r}): {ex}")
        return None
    finally:
        db.close()


def _save_session(sid: str, data: dict) -> None:
    """Сохранить данные сессии в БД (upsert)."""
    try:
        db = _get_session_factory()()
        row = db.query(DbSessionModel).filter(DbSessionModel.session_id == sid).first()
        if row is None:
            row = DbSessionModel(session_id=sid, data=json.dumps(data))
            db.add(row)
        else:
            row.data = json.dumps(data)
        db.commit()
    except Exception as ex:
        print(f"[WARN] _save_session({sid!r}): {ex}")
        db.rollback()
    finally:
        db.close()
