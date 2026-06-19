"""Seed-данные: группы упражнений и сами упражнения."""

from app.models import ExerciseGroup, Exercise


EXERCISES = {
    "СПИНА": [
        "Подтягивания прямым хватом",
        "Подтягивания обратным хватом",
        "Тяга штанги в наклоне",
        "Тяга гантели в наклоне",
        "Тяга блока горизонтальная",
        "Тяга верхнего блока широким хватом",
        "Тяга верхнего блока узким хватом",
        "Shrugs (штанга)",
        "Shrugs (гантели)",
        "Гиперэкстензия",
    ],
    "ГРУДЬ": [
        "Жим штанги лёжа",
        "Жим гантелей лёжа",
        "Жим штанги на наклонной скамье",
        "Жим гантелей на наклонной скамье",
        "Разводка гантелей лёжа",
        "Сведение рук в кроссовере",
        "Отжимания от брусьев",
        "Отжимания от пола",
    ],
    "НОГИ": [
        "Приседания со штангой",
        "Приседания в гакк-машине",
        "Жим ногами",
        "Становая тяга",
        "Румынская тяга",
        "Сгибание ног лёжа",
        "Разгибание ног сидя",
        "Выпады с гантелями",
        "Ягодичный мостик",
        "Подъём на носки стоя",
        "Подъём на носки сидя",
    ],
    "ПЛЕЧИ": [
        "Жим штанги стоя",
        "Жим гантелей сидя",
        "Махи гантелями в стороны",
        "Махи гантелями перед собой",
        "Махи гантелями в наклоне",
        "Тяга штанги к подбородку",
        "Армейский жим",
    ],
    "РУКИ (БИЦЕПС)": [
        "Подъём штанги на бицепс стоя",
        "Подъём гантелей на бицепс стоя",
        "Концентрированный подъём гантели",
        "Сгибание рук с гантелью на скамье Скотта",
        "Молотковые сгибания",
    ],
    "РУКИ (ТРИЦЕПС)": [
        "Французский жим лёжа",
        "Французский жим сидя",
        "Разгибание рук на блоке",
        "Разгибание гантели из-за головы",
        "Отжимания от скамьи",
    ],
    "ПРЕСС": [
        "Скручивания лёжа",
        "Подъём ног в висе",
        "Подъём ног лёжа",
        "Планка",
        "Косые скручивания",
        "Велосипед",
        "Русский твист",
    ],
}


def seed_exercises(db):
    """Добавить группы и упражнения в БД, если их ещё нет."""
    if db.query(ExerciseGroup).count() > 0:
        return  # уже заполнено

    for order, (group_name, exercises) in enumerate(EXERCISES.items(), start=1):
        group = ExerciseGroup(name=group_name, sort_order=order)
        db.add(group)
        db.flush()  # чтобы получить group.id
        for eo, ex_name in enumerate(exercises, start=1):
            db.add(Exercise(group_id=group.id, name=ex_name, sort_order=eo))

    db.commit()


def ensure_exercises(db):
    """Добавить отсутствующие группы/упражнения в существующую БД."""
    sort_order = db.query(ExerciseGroup).count()
    for group_name, exercise_names in EXERCISES.items():
        g = db.query(ExerciseGroup).filter(ExerciseGroup.name == group_name).first()
        if not g:
            sort_order += 1
            g = ExerciseGroup(name=group_name, sort_order=sort_order)
            db.add(g)
            db.flush()
        existing_names = {e.name for e in db.query(Exercise).filter(Exercise.group_id == g.id).all()}
        max_sort = db.query(Exercise).filter(Exercise.group_id == g.id).count()
        for ex_name in exercise_names:
            if ex_name not in existing_names:
                max_sort += 1
                db.add(Exercise(group_id=g.id, name=ex_name, sort_order=max_sort))
    db.commit()
