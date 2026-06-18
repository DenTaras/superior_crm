"""API для конструктора тренировок: группы, упражнения, лог клиента."""

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import ExerciseGroup, Exercise, ClientExerciseLog
from app.auth import require_role

router = APIRouter()


@router.get("/api/exercise-groups")
def api_exercise_groups(
    _: dict = Depends(require_role("admin", "trainer")),
    db: Session = Depends(get_db),
):
    """Список групп упражнений."""
    groups = db.query(ExerciseGroup).order_by(ExerciseGroup.sort_order).all()
    return [{"id": g.id, "name": g.name} for g in groups]


@router.get("/api/exercises")
def api_exercises(
    group_id: int = Query(...),
    _: dict = Depends(require_role("admin", "trainer")),
    db: Session = Depends(get_db),
):
    """Список упражнений в группе."""
    exercises = (
        db.query(Exercise)
        .filter(Exercise.group_id == group_id)
        .order_by(Exercise.sort_order)
        .all()
    )
    return [{"id": e.id, "name": e.name} for e in exercises]


@router.get("/api/exercise-log")
def api_exercise_log(
    client_id: int = Query(...),
    exercise_id: int = Query(...),
    _: dict = Depends(require_role("admin", "trainer")),
    db: Session = Depends(get_db),
):
    """Последняя запись лога упражнения для клиента (для прогрессии)."""
    log = (
        db.query(ClientExerciseLog)
        .filter(
            ClientExerciseLog.client_id == client_id,
            ClientExerciseLog.exercise_id == exercise_id,
        )
        .order_by(ClientExerciseLog.created_at.desc())
        .first()
    )
    if log:
        # Прогрессия +5%
        new_weight = round(log.weight * 1.05) if log.weight else 0
        new_reps = round(log.reps * 1.05) if log.reps else 0
        return {
            "found": True,
            "last_weight": log.weight,
            "last_reps": log.reps,
            "last_sets": log.sets,
            "suggested_weight": new_weight,
            "suggested_reps": new_reps,
        }
    return {"found": False}


class LogSaveRequest(BaseModel):
    client_id: int
    exercise_id: int
    weight: int = 0
    reps: int = 0
    sets: int = 0


@router.post("/api/exercise-log")
def api_exercise_log_save(
    body: LogSaveRequest,
    _: dict = Depends(require_role("admin", "trainer")),
    db: Session = Depends(get_db),
):
    """Сохранить запись в лог упражнения клиента."""
    log = ClientExerciseLog(
        client_id=body.client_id,
        exercise_id=body.exercise_id,
        weight=body.weight,
        reps=body.reps,
        sets=body.sets,
    )
    db.add(log)
    db.commit()
    return {"ok": True}
