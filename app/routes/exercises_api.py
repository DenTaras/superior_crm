"""API для конструктора тренировок: группы, упражнения, план, лог клиента."""

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import ExerciseGroup, Exercise, ClientExerciseLog, TrainingPlanExercise
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


# ---- Упражнения в плане тренировки (слот + клиент) ----


@router.get("/api/plan-exercises")
def api_plan_exercises(
    slot_id: int = Query(...),
    client_id: int = Query(...),
    _: dict = Depends(require_role("admin", "trainer")),
    db: Session = Depends(get_db),
):
    """Список упражнений в плане тренировки для слота/клиента."""
    items = (
        db.query(TrainingPlanExercise, Exercise)
        .join(Exercise, TrainingPlanExercise.exercise_id == Exercise.id)
        .filter(
            TrainingPlanExercise.slot_id == slot_id,
            TrainingPlanExercise.client_id == client_id,
        )
        .order_by(TrainingPlanExercise.sort_order)
        .all()
    )
    return [
        {
            "id": tpe.id,
            "exercise_id": tpe.exercise_id,
            "exercise_name": ex.name,
            "weight": tpe.weight,
            "target_reps": tpe.target_reps,
            "actual_reps": tpe.actual_reps,
            "sets": tpe.sets,
            "sort_order": tpe.sort_order,
        }
        for tpe, ex in items
    ]


class PlanExerciseAdd(BaseModel):
    slot_id: int
    client_id: int
    exercise_id: int
    weight: int = 0
    target_reps: int = 0
    sets: int = 0


@router.post("/api/plan-exercises/add")
def api_plan_exercises_add(
    body: PlanExerciseAdd,
    _: dict = Depends(require_role("admin", "trainer")),
    db: Session = Depends(get_db),
):
    """Добавить упражнение в план тренировки."""
    max_order = (
        db.query(TrainingPlanExercise.sort_order)
        .filter(
            TrainingPlanExercise.slot_id == body.slot_id,
            TrainingPlanExercise.client_id == body.client_id,
        )
        .order_by(TrainingPlanExercise.sort_order.desc())
        .first()
    )
    sort_order = (max_order[0] or 0) + 1 if max_order else 1

    tpe = TrainingPlanExercise(
        slot_id=body.slot_id,
        client_id=body.client_id,
        exercise_id=body.exercise_id,
        weight=body.weight,
        target_reps=body.target_reps,
        sets=body.sets,
        sort_order=sort_order,
    )
    db.add(tpe)
    db.commit()
    return {"ok": True, "id": tpe.id}


class PlanExerciseUpdate(BaseModel):
    id: int
    actual_reps: int | None = None


@router.post("/api/plan-exercises/update")
def api_plan_exercises_update(
    body: PlanExerciseUpdate,
    _: dict = Depends(require_role("admin", "trainer")),
    db: Session = Depends(get_db),
):
    """Обновить фактические повторения в упражнении плана."""
    tpe = db.get(TrainingPlanExercise, body.id)
    if not tpe:
        return JSONResponse({"ok": False}, status_code=404)
    tpe.actual_reps = body.actual_reps
    db.add(tpe)
    db.commit()
    return {"ok": True}


@router.post("/api/plan-exercises/delete/{item_id}")
def api_plan_exercises_delete(
    item_id: int,
    _: dict = Depends(require_role("admin", "trainer")),
    db: Session = Depends(get_db),
):
    """Удалить упражнение из плана."""
    tpe = db.get(TrainingPlanExercise, item_id)
    if tpe:
        db.delete(tpe)
        db.commit()
    return {"ok": True}
