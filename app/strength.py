"""Расчёт силовых показателей и нормативы."""

import math

# ---- Ключевые упражнения для силовых показателей ----
KEY_EXERCISES = {
    "Становая тяга": "deadlift",
    "Приседания со штангой": "squat",
    "Жим штанги лёжа": "bench",
    "Жим штанги стоя": "ohp",
    "Подтягивания прямым хватом": "pullup",
    "Отжимания от брусьев": "dips",
}


def epley_1rm(weight: int, reps: int) -> int:
    """Расчёт одноповторного максимума по формуле Эпли.
    weight — вес в кг, reps — количество повторений (1-30).
    """
    if reps <= 0 or weight <= 0:
        return 0
    return round(weight * (1 + reps / 30))


def estimate_1rm(weight: int, reps: int) -> int:
    """Оценить 1ПМ: если reps == 1 — это фактический 1ПМ, иначе по Эпли."""
    if reps <= 0 or weight <= 0:
        return 0
    if reps == 1:
        return weight
    return epley_1rm(weight, reps)


# ---- Нормативы (разряды) для мужчин, кг ----
# Источник: основано на IPF/FPR стандартах (примерные значения)
# Ключ: (пол, упражнение) -> список (разряд, мин_вес_атлета, макс_вес_атлета, норматив_кг)
# Разряды: МСМК, МС, КМС, 1 разряд, 2 разряд, 3 разряд

STANDARDS = {
    # Мужчины, без экипировки
    ("male", "bench"): [
        ("МСМК", 0, 999, 1.50),
        ("МС", 0, 999, 1.30),
        ("КМС", 0, 999, 1.10),
        ("1 разряд", 0, 999, 0.90),
        ("2 разряд", 0, 999, 0.70),
        ("3 разряд", 0, 999, 0.55),
    ],
    ("male", "squat"): [
        ("МСМК", 0, 999, 2.20),
        ("МС", 0, 999, 1.90),
        ("КМС", 0, 999, 1.60),
        ("1 разряд", 0, 999, 1.30),
        ("2 разряд", 0, 999, 1.00),
        ("3 разряд", 0, 999, 0.80),
    ],
    ("male", "deadlift"): [
        ("МСМК", 0, 999, 2.50),
        ("МС", 0, 999, 2.20),
        ("КМС", 0, 999, 1.80),
        ("1 разряд", 0, 999, 1.50),
        ("2 разряд", 0, 999, 1.20),
        ("3 разряд", 0, 999, 0.95),
    ],
    ("male", "ohp"): [
        ("МСМК", 0, 999, 0.95),
        ("МС", 0, 999, 0.80),
        ("КМС", 0, 999, 0.65),
        ("1 разряд", 0, 999, 0.55),
        ("2 разряд", 0, 999, 0.45),
        ("3 разряд", 0, 999, 0.35),
    ],
    ("male", "pullup"): [
        ("МСМК", 0, 999, 0.80),
        ("МС", 0, 999, 0.65),
        ("КМС", 0, 999, 0.50),
        ("1 разряд", 0, 999, 0.40),
        ("2 разряд", 0, 999, 0.30),
        ("3 разряд", 0, 999, 0.20),
    ],
    ("male", "dips"): [
        ("МСМК", 0, 999, 1.30),
        ("МС", 0, 999, 1.10),
        ("КМС", 0, 999, 0.90),
        ("1 разряд", 0, 999, 0.70),
        ("2 разряд", 0, 999, 0.55),
        ("3 разряд", 0, 999, 0.40),
    ],
}


def get_rank(sex: str, exercise_key: str, body_weight: int, one_rm: int) -> str | None:
    """Определить разряд для упражнения."""
    key = (sex, exercise_key)
    standards = STANDARDS.get(key)
    if not standards or body_weight <= 0 or one_rm <= 0:
        return None
    ratio = one_rm / body_weight
    for rank_name, _, _, req_ratio in standards:
        if ratio >= req_ratio:
            return rank_name
    return None


def collect_strength_data(db_session, client_id: int, sex: str = "male"):
    """Собрать силовые показатели клиента из лога упражнений."""
    from app.models import ClientExerciseLog, Exercise

    results = []
    for ex_name, ex_key in KEY_EXERCISES.items():
        # Ищем упражнение в БД
        exercise = (
            db_session.query(Exercise)
            .filter(Exercise.name == ex_name)
            .first()
        )
        if not exercise:
            results.append({
                "name": ex_name,
                "key": ex_key,
                "one_rm": None,
                "rank": None,
                "source": None,
            })
            continue

        # Берём последнюю запись лога для этого упражнения
        log_entry = (
            db_session.query(ClientExerciseLog)
            .filter(
                ClientExerciseLog.client_id == client_id,
                ClientExerciseLog.exercise_id == exercise.id,
            )
            .order_by(ClientExerciseLog.created_at.desc())
            .first()
        )

        one_rm = None
        source = None
        if log_entry:
            one_rm = estimate_1rm(log_entry.weight, log_entry.reps)
            source = f"{log_entry.weight} кг × {log_entry.reps} повторений"

        results.append({
            "name": ex_name,
            "key": ex_key,
            "one_rm": one_rm,
            "source": source,
        })

    return results


def enrich_with_rank(results, sex: str, body_weight: int):
    """Добавить нормативы к результатам."""
    for r in results:
        if r["one_rm"] and body_weight > 0:
            r["rank"] = get_rank(sex, r["key"], body_weight, r["one_rm"])
        else:
            r["rank"] = None
    return results


# ---- Нормативная таблица для отображения клиенту ----
RANK_NAMES = ["МСМК", "МС", "КМС", "1 разряд", "2 разряд", "3 разряд"]


def compute_standards_table(sex: str, body_weight: int) -> list:
    """Рассчитать таблицу нормативов для веса клиента.

    Возвращает список упражнений с указанием веса штанги для каждого разряда.
    """
    if body_weight <= 0:
        return []

    table = []
    for ex_name, ex_key in KEY_EXERCISES.items():
        key = (sex, ex_key)
        standards = STANDARDS.get(key)
        if not standards:
            continue
        row = {"name": ex_name}
        for rank_name, _, _, req_ratio in standards:
            required_weight = round(req_ratio * body_weight)
            row[rank_name] = required_weight
        table.append(row)
    return table
