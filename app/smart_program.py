"""Smart-конструктор тренировки: автоматическая генерация программы по сплитам.

Логика:
1. Для каждого сплита определён пул базовых и изолирующих упражнений.
2. При генерации выбираются упражнения, которые не использовались в последних
   тренировках клиента (ротация). Если все перебраны — начинается новый цикл.
3. Вес подбирается по прогрессии +5% от последнего выполнения (или 0, если новое).
4. Итог: 5 упражнений × 3 подхода = 15 подходов, диапазон 8-12 повторений.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import Exercise, ClientExerciseLog, TrainingPlanExercise
from app.auth import require_role

router = APIRouter()

# ---- Пул упражнений для каждого сплита ----
# Каждый элемент: (название упражнения, тип: compound/isolation)
# Названия должны точно соответствовать именам в seed_exercises.py

SPLIT_EXERCISES = {
    "legs_shoulders": {
        "name": "Сплит — Ноги+Плечи",
        "compound": [
            "Приседания со штангой",
            "Становая тяга",
            "Румынская тяга",
            "Выпады с гантелями",
            "Ягодичный мостик",
            "Жим ногами",
            "Жим штанги стоя",
            "Жим гантелей сидя",
            "Армейский жим",
        ],
        "isolation": [
            "Сгибание ног лёжа",
            "Разгибание ног сидя",
            "Подъём на носки стоя",
            "Подъём на носки сидя",
            "Махи гантелями в стороны",
            "Махи гантелями перед собой",
            "Махи гантелями в наклоне",
            "Тяга штанги к подбородку",
        ],
    },
    "chest": {
        "name": "Сплит — Грудь",
        "compound": [
            "Жим штанги лёжа",
            "Жим гантелей лёжа",
            "Жим штанги на наклонной скамье",
            "Жим гантелей на наклонной скамье",
            "Отжимания от брусьев",
        ],
        "isolation": [
            "Разводка гантелей лёжа",
            "Сведение рук в кроссовере",
            "Отжимания от пола",
        ],
    },
    "back": {
        "name": "Сплит — Спина",
        "compound": [
            "Подтягивания прямым хватом",
            "Подтягивания обратным хватом",
            "Тяга штанги в наклоне",
            "Тяга гантели в наклоне",
        ],
        "isolation": [
            "Тяга блока горизонтальная",
            "Тяга верхнего блока широким хватом",
            "Тяга верхнего блока узким хватом",
            "Shrugs (штанга)",
            "Shrugs (гантели)",
            "Гиперэкстензия",
        ],
    },
    "fullbody": {
        "name": "Фулбади",
        "compound": [
            "Приседания со штангой",
            "Жим штанги лёжа",
            "Тяга штанги в наклоне",
            "Жим штанги стоя",
            "Подтягивания прямым хватом",
            "Становая тяга",
            "Жим гантелей лёжа",
        ],
        "isolation": [
            "Махи гантелями в стороны",
            "Сгибание ног лёжа",
            "Разводка гантелей лёжа",
            "Подъём штанги на бицепс стоя",
            "Французский жим лёжа",
        ],
    },
}


def _get_recent_exercise_ids(db: Session, client_id: int, limit: int = 20):
    """Вернуть ID упражнений, которые клиент делал в последних тренировках."""
    rows = (
        db.query(TrainingPlanExercise.exercise_id)
        .filter(TrainingPlanExercise.client_id == client_id)
        .order_by(desc(TrainingPlanExercise.created_at))
        .limit(limit)
        .all()
    )
    return {r[0] for r in rows}


def _resolve_exercise_id(db: Session, name: str) -> int | None:
    """Найти ID упражнения по точному названию."""
    ex = db.query(Exercise).filter(Exercise.name == name).first()
    return ex.id if ex else None


def _get_suggested_weight(db: Session, client_id: int, exercise_id: int) -> tuple[int, int, int]:
    """Вернуть (предлагаемый_вес, целевые_повторы, количество_подходов).

    Если упражнение выполнялось ранее — +5% к последнему весу.
    Если нет — вес 0 (рекомендуется начать с минимального).
    """
    log = (
        db.query(ClientExerciseLog)
        .filter(
            ClientExerciseLog.client_id == client_id,
            ClientExerciseLog.exercise_id == exercise_id,
        )
        .order_by(ClientExerciseLog.created_at.desc())
        .first()
    )
    if log and log.weight and log.weight > 0:
        new_weight = max(1, round(log.weight * 1.05))
        new_reps = log.reps or 10
        new_sets = log.sets or 3
        return new_weight, new_reps, new_sets
    return 0, 10, 3


class SmartProgramRequest(BaseModel):
    slot_id: int
    client_id: int
    split: str  # legs_shoulders | chest | back | fullbody


@router.post("/api/smart-program")
def api_smart_program(
    body: SmartProgramRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin", "trainer")),
):
    """Сгенерировать программу тренировки по сплиту."""
    split_config = SPLIT_EXERCISES.get(body.split)
    if not split_config:
        return JSONResponse({"ok": False, "error": "Unknown split"}, status_code=400)

    # Какие упражнения уже использовались недавно
    recent_ids = _get_recent_exercise_ids(db, body.client_id)

    # Выбираем 3 базовых + 2 изолирующих (всего 5 упражнений)
    # С ротацией: предпочитаем те, что НЕ в recent_ids
    def pick_exercises(pool, count):
        candidates = []
        for name in pool:
            ex_id = _resolve_exercise_id(db, name)
            if ex_id is None:
                continue
            candidates.append((name, ex_id))

        # Сортируем: сначала те, что НЕ были в recent_ids (ротация)
        fresh = [(n, eid) for n, eid in candidates if eid not in recent_ids]
        used = [(n, eid) for n, eid in candidates if eid in recent_ids]

        selected = fresh[:count]
        if len(selected) < count:
            # Добираем из уже использованных (начало нового цикла)
            remaining = count - len(selected)
            selected += used[:remaining]

        return selected

    selected_compound = pick_exercises(split_config["compound"], 3)
    selected_isolation = pick_exercises(split_config["isolation"], 2)

    all_selected = selected_compound + selected_isolation  # 5 упражнений

    if len(all_selected) < 5:
        return JSONResponse({"ok": False, "error": "Недостаточно упражнений в БД"}, status_code=400)

    # Определяем максимальный sort_order для текущего плана
    max_order = (
        db.query(TrainingPlanExercise.sort_order)
        .filter(
            TrainingPlanExercise.slot_id == body.slot_id,
            TrainingPlanExercise.client_id == body.client_id,
        )
        .order_by(desc(TrainingPlanExercise.sort_order))
        .first()
    )
    next_order = (max_order[0] or 0) + 1 if max_order else 1

    created = []
    for exercise_name, exercise_id in all_selected:
        weight, target_reps, _ = _get_suggested_weight(db, body.client_id, exercise_id)
        # Целевые повторы в диапазоне 8-12
        if target_reps < 8:
            target_reps = 8
        elif target_reps > 12:
            target_reps = 12

        # 3 подхода, каждый как отдельная запись
        for s in range(3):
            tpe = TrainingPlanExercise(
                slot_id=body.slot_id,
                client_id=body.client_id,
                exercise_id=exercise_id,
                weight=weight,
                target_reps=target_reps,
                sets=1,
                sort_order=next_order,
            )
            db.add(tpe)
            db.flush()
            created.append({
                "id": tpe.id,
                "exercise_name": exercise_name,
                "weight": weight,
                "target_reps": target_reps,
                "sets": 1,
            })
            next_order += 1

    db.commit()
    return {"ok": True, "exercises": created}
