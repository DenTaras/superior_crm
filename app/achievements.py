"""Достижения клиентов — геймификация силовых тренировок.

Достижения вычисляются на основе данных в БД (лог упражнений, антропометрия, журнал)
и сохраняются в таблицу achievements.
"""

from datetime import datetime, timedelta
from sqlalchemy import func, desc
from app.models import Achievement, ClientExerciseLog, AnthropometryLog, JournalEntry, Exercise, Client
from app.timezone import now as tz_now


# ---- Определения достижений ----
# (category, icon, title_format, check_fn)
# check_fn(client_id, db) -> (title, description) or None

STRENGTH_MILESTONES = {
    "Жим штанги лёжа": [
        (60, "💪", "Жим лёжа 60 кг", "Первый серьёзный рубеж! Вы пожали 60 кг."),
        (80, "🔥", "Жим лёжа 80 кг", "Отличный результат! 80 кг покорились."),
        (100, "🏋️", "Жим лёжа 100 кг", "Сотня в жиме! Вы вошли в клуб сильных."),
        (120, "💎", "Жим лёжа 120 кг", "Элитный уровень! 120 кг — мощь!"),
    ],
    "Приседания со штангой": [
        (80, "💪", "Присед 80 кг", "Первый рубеж в приседаниях!"),
        (100, "🔥", "Присед 100 кг", "Сотня в приседе! Отличная база."),
        (120, "🏋️", "Присед 120 кг", "120 кг в приседе — серьёзная сила."),
        (140, "💎", "Присед 140 кг", "Элитный присед! 140 кг!"),
    ],
    "Становая тяга": [
        (80, "💪", "Становая 80 кг", "Первый рубеж в становой!"),
        (100, "🔥", "Становая 100 кг", "Сотня в становой — отличная тяга!"),
        (120, "🏋️", "Становая 120 кг", "120 кг — мощная тяга!"),
        (140, "💎", "Становая 140 кг", "140 кг! Вы очень сильны!"),
    ],
}

BODY_ACHIEVEMENTS = [
    ("weight_loss_5", "📉", "Минус 5 кг", "Потеряли 5 кг с начала занятий! Отличный старт."),
    ("weight_loss_10", "📉", "Минус 10 кг", "Минус 10 кг! Серьёзная трансформация."),
    ("fat_loss_3", "🎯", "Минус 3% жира", "Снизили процент жира на 3%!"),
    ("fat_loss_5", "🎯", "Минус 5% жира", "Снизили процент жира на 5%! Видимый результат."),
]

DISCIPLINE_ACHIEVEMENTS = [
    (12, "📅", "Месяц дисциплины", "12+ тренировок за месяц — стабильность!"),
    (24, "📅", "2 месяца дисциплины", "24+ тренировок за 2 месяца — привычка сформирована."),
    (50, "🌟", "50 тренировок", "50 тренировок позади! Настоящий атлет."),
    (100, "💫", "100 тренировок", "100 тренировок! Железная дисциплина."),
]


def _get_best_1rm(db, client_id: int, exercise_name: str) -> int | None:
    """Вернуть лучший 1ПМ для упражнения (по формуле Эпли)."""
    log = (
        db.query(ClientExerciseLog)
        .join(Exercise, ClientExerciseLog.exercise_id == Exercise.id)
        .filter(
            ClientExerciseLog.client_id == client_id,
            Exercise.name == exercise_name,
            ClientExerciseLog.weight > 0,
        )
        .order_by(desc(ClientExerciseLog.weight))
        .first()
    )
    if not log:
        return None
    # Формула Эпли: вес × (1 + повторы / 30)
    if log.reps and log.reps > 1:
        return round(log.weight * (1 + log.reps / 30))
    return log.weight


def _check_strength_achievements(client_id: int, db) -> list[dict]:
    """Проверить силовые достижения."""
    earned = []
    existing = {
        a.title for a in db.query(Achievement).filter(
            Achievement.client_id == client_id,
            Achievement.category == "strength",
        ).all()
    }

    for exercise_name, milestones in STRENGTH_MILESTONES.items():
        best_1rm = _get_best_1rm(db, client_id, exercise_name)
        if best_1rm is None:
            continue
        for threshold, icon, title, desc in milestones:
            if best_1rm >= threshold and title not in existing:
                earned.append({
                    "category": "strength",
                    "icon": icon,
                    "title": title,
                    "description": desc,
                })
    return earned


def _check_body_achievements(client_id: int, db) -> list[dict]:
    """Проверить достижения по антропометрии."""
    earned = []
    existing = {
        a.title for a in db.query(Achievement).filter(
            Achievement.client_id == client_id,
            Achievement.category == "body",
        ).all()
    }

    logs = (
        db.query(AnthropometryLog)
        .filter(AnthropometryLog.client_id == client_id, AnthropometryLog.weight_kg.isnot(None))
        .order_by(AnthropometryLog.created_at)
        .all()
    )
    if len(logs) >= 2:
        first_w = logs[0].weight_kg
        last_w = logs[-1].weight_kg
        loss = first_w - last_w
        if loss >= 5 and "Минус 5 кг" not in existing:
            earned.append({"category": "body", "icon": "📉", "title": "Минус 5 кг",
                           "description": f"Потеряли 5 кг с начала занятий ({first_w}→{last_w} кг)! Отличный старт."})
        if loss >= 10 and "Минус 10 кг" not in existing:
            earned.append({"category": "body", "icon": "📉", "title": "Минус 10 кг",
                           "description": f"Минус 10 кг! Серьёзная трансформация ({first_w}→{last_w} кг)."})

    # % жира
    fat_logs = (
        db.query(AnthropometryLog)
        .filter(AnthropometryLog.client_id == client_id, AnthropometryLog.body_fat.isnot(None))
        .order_by(AnthropometryLog.created_at)
        .all()
    )
    if len(fat_logs) >= 2:
        first_f = fat_logs[0].body_fat
        last_f = fat_logs[-1].body_fat
        fat_loss = first_f - last_f
        if fat_loss >= 3 and "Минус 3% жира" not in existing:
            earned.append({"category": "body", "icon": "🎯", "title": "Минус 3% жира",
                           "description": f"Снизили процент жира на 3% ({first_f}%→{last_f}%)!"})
        if fat_loss >= 5 and "Минус 5% жира" not in existing:
            earned.append({"category": "body", "icon": "🎯", "title": "Минус 5% жира",
                           "description": f"Снизили процент жира на 5% ({first_f}%→{last_f}%)! Видимый результат."})

    return earned


def _check_discipline_achievements(client_id: int, db) -> list[dict]:
    """Проверить достижения по дисциплине (количество тренировок)."""
    earned = []
    existing = {
        a.title for a in db.query(Achievement).filter(
            Achievement.client_id == client_id,
            Achievement.category == "discipline",
        ).all()
    }

    c = db.query(Client).filter(Client.id == client_id).first()
    if not c:
        return earned
    c_name = c.fio()

    total_sessions = db.query(JournalEntry).filter(
        JournalEntry.clients.contains(c_name)
    ).count()

    for threshold, icon, title, desc_tpl in DISCIPLINE_ACHIEVEMENTS:
        if total_sessions >= threshold and title not in existing:
            earned.append({
                "category": "discipline",
                "icon": icon,
                "title": title,
                "description": f"{desc_tpl} ({total_sessions} тренировок)",
            })

    return earned


def compute_achievements(client_id: int, db):
    """Вычислить и сохранить новые достижения для клиента."""
    all_new = []
    all_new += _check_strength_achievements(client_id, db)
    all_new += _check_body_achievements(client_id, db)
    all_new += _check_discipline_achievements(client_id, db)

    now = tz_now()
    for a in all_new:
        ach = Achievement(
            client_id=client_id,
            category=a["category"],
            icon=a["icon"],
            title=a["title"],
            description=a["description"],
            achieved_at=now,
        )
        db.add(ach)
    if all_new:
        db.commit()

    return all_new


def get_achievements(client_id: int, db) -> list[Achievement]:
    """Получить все достижения клиента, отсортированные по дате."""
    return (
        db.query(Achievement)
        .filter(Achievement.client_id == client_id)
        .order_by(desc(Achievement.achieved_at))
        .all()
    )
