"""Сгенерировать 2 месяца тренировок с прогрессией для демонстрации графиков.

Запуск: python scripts/seed_history.py
Создаёт записи ClientExerciseLog и JournalEntry для каждого клиента.
"""

import sys
import os
from datetime import datetime, timedelta
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models import Client, Exercise, ClientExerciseLog, JournalEntry, AnthropometryLog

random.seed(42)

# ---- Программа тренировок для каждого клиента ----
# (название упражнения, начальный вес, прогрессия за 2 месяца: итоговый вес)
# Прогрессия: +5% каждые 3 тренировки (~1 раз в неделю)

# ---- Антропометрия: начальные и конечные значения за 2 месяца ----
# Формат: (вес, %жира, талия, грудь, плечи, бицепс, бедро, шея,
#           складка_грудь, складка_живот, складка_бедро, складка_трицепс, складка_под_лопаткой)
ANTHRO = {
    1: {  # Петров Иван — набирает мышечную массу
        "start": (88, 18, 88, 105, 120, 35, 58, 40, 8, 14, 12, 10, 11),
        "end":   (90, 15, 84, 110, 124, 37, 56, 40, 6, 11, 10, 8, 9),
    },
    2: {  # Иванова Мария — худеет + подтяжка
        "start": (50, 25, 72, 88, 100, 26, 62, 33, 10, 18, 16, 14, 12),
        "end":   (49, 21, 66, 90, 102, 28, 60, 33, 7, 14, 12, 10, 9),
    },
    3: {  # Сидоров Алексей — набор массы
        "start": (75, 20, 82, 100, 115, 33, 56, 39, 9, 16, 14, 11, 10),
        "end":   (77, 17, 78, 105, 119, 35, 55, 39, 6, 12, 11, 8, 8),
    },
    4: {  # Васильев Василий — рекомпозиция
        "start": (82, 22, 86, 102, 118, 34, 57, 40, 11, 18, 15, 12, 13),
        "end":   (83, 18, 80, 108, 122, 36, 55, 40, 7, 13, 11, 9, 9),
    },
}

PROGRAMS = {
    # Петров Иван — фулбади
    1: {
        "base_weight": 88,
        "exercises": [
            ("Жим штанги лёжа",         60, 85),
            ("Приседания со штангой",    70, 100),
            ("Тяга штанги в наклоне",    50, 72),
            ("Жим штанги стоя",          30, 44),
            ("Подтягивания прямым хватом", 0, 0),  # bodyweight
            ("Сгибание ног лёжа",        35, 50),
            ("Подъём штанги на бицепс стоя", 20, 30),
            ("Французский жим лёжа",     20, 30),
        ],
    },
    # Иванова Мария — ноги+ягодицы + верх
    2: {
        "base_weight": 50,
        "exercises": [
            ("Приседания со штангой",    30, 48),
            ("Румынская тяга",           25, 40),
            ("Ягодичный мостик",         20, 36),
            ("Жим гантелей лёжа",        12, 20),
            ("Тяга верхнего блока широким хватом", 20, 32),
            ("Выпады с гантелями",       10, 18),
            ("Махи гантелями в стороны",  4, 8),
        ],
    },
    # Сидоров Алексей — жим+тяга
    3: {
        "base_weight": 75,
        "exercises": [
            ("Жим штанги лёжа",         50, 72),
            ("Тяга штанги в наклоне",    45, 65),
            ("Жим гантелей сидя",        16, 26),
            ("Тяга верхнего блока узким хватом", 35, 52),
            ("Разводка гантелей лёжа",   10, 18),
            ("Подтягивания обратным хватом", 0, 0),
            ("Скручивания лёжа",         0, 0),
        ],
    },
    # Васильев Василий — ноги+плечи
    4: {
        "base_weight": 82,
        "exercises": [
            ("Приседания со штангой",    60, 86),
            ("Становая тяга",            65, 92),
            ("Жим гантелей сидя",        18, 28),
            ("Махи гантелями в стороны",  6, 11),
            ("Сгибание ног лёжа",        30, 44),
            ("Разгибание ног сидя",      35, 50),
            ("Махи гантелями в наклоне",  8, 14),
        ],
    },
}

# График: 3 тренировки в неделю (ПН, СР, ПТ) за последние 8 недель
WEEKDAYS = [0, 2, 4]  # Mon, Wed, Fri


def _weight_for_session(start_w, end_w, session_idx, total_sessions):
    """Вес на конкретной тренировке: линейная интерполяция с небольшим шумом."""
    if start_w == 0 and end_w == 0:
        return 0  # bodyweight
    progress = session_idx / max(total_sessions - 1, 1)
    w = start_w + (end_w - start_w) * progress
    # небольшой шум ±2%
    noise = random.uniform(-0.02, 0.02) * w
    return max(0, round(w + noise))


def seed_history():
    db = SessionLocal()

    # Задаём вес клиентам, у кого нет
    for cid in (3, 4):
        c = db.get(Client, cid)
        if c and not c.weight_kg:
            c.weight_kg = PROGRAMS[cid]["base_weight"]
            db.add(c)
    db.commit()

    now = datetime.now()
    total_sessions = 8 * 3  # 8 weeks × 3 times = 24 sessions

    for client_id, program in PROGRAMS.items():
        client = db.get(Client, client_id)
        if not client:
            continue

        print(f"\n=== {client.fio()} (id={client_id}) ===")

        # Очищаем старые данные для этого клиента
        db.query(ClientExerciseLog).filter(
            ClientExerciseLog.client_id == client_id
        ).delete()
        db.query(JournalEntry).filter(
            JournalEntry.clients.contains(client.fio())
        ).delete()
        db.commit()

        session_dates = []

        # Генерируем 24 даты тренировок (ПН, СР, ПТ) за последние 8 недель
        week_start = (now - timedelta(weeks=8)).replace(hour=10, minute=0, second=0, microsecond=0)
        # Сдвигаем к ближайшему ПН
        week_start -= timedelta(days=week_start.weekday())

        for week in range(8):
            for wd in WEEKDAYS:
                d = week_start + timedelta(weeks=week, days=wd)
                if d < now:
                    session_dates.append(d)

        session_dates = session_dates[:total_sessions]

        exercise_ids = {}
        for ex_name, _, _ in program["exercises"]:
            ex = db.query(Exercise).filter(Exercise.name == ex_name).first()
            if ex:
                exercise_ids[ex_name] = ex.id
            else:
                print(f"  ⚠ Упражнение '{ex_name}' не найдено в БД, пропускаю")

        # Для каждого упражнения генерируем логи
        for ex_name, start_w, end_w in program["exercises"]:
            ex_id = exercise_ids.get(ex_name)
            if not ex_id:
                continue

            # Определяем сколько подходов
            if ex_name in ("Подтягивания прямым хватом", "Подтягивания обратным хватом"):
                sets_per_session = 3
            elif ex_name in ("Скручивания лёжа", "Планка"):
                sets_per_session = 3
            else:
                sets_per_session = 4

            print(f"  {ex_name}: {start_w}→{end_w} кг, {len(session_dates)} тренировок")

            for si, session_date in enumerate(session_dates):
                weight = _weight_for_session(start_w, end_w, si, len(session_dates))

                # Повторы: 8-12, со временем могут немного расти
                base_reps = 8 + (si // 6)  # увеличиваем на 1 каждые 6 сессий
                reps = min(base_reps + random.choice([0, 0, 1, 1, 2]), 15)

                for set_n in range(sets_per_session):
                    # Небольшая вариация веса по подходам: -2, 0, 0, +2 кг
                    set_weight = max(0, weight + [-2, 0, 0, 2][min(set_n, 3)])
                    log = ClientExerciseLog(
                        client_id=client_id,
                        exercise_id=ex_id,
                        weight=set_weight,
                        reps=reps,
                        sets=1,
                        created_at=session_date + timedelta(minutes=set_n * 3),
                    )
                    db.add(log)

        db.commit()

        # Создаём записи в журнале (чтобы была "История тренировок")
        for si, session_date in enumerate(session_dates):
            # Собираем имена упражнений на эту тренировку (3-4 упражнения за раз)
            ex_names = [name for name, _, _ in program["exercises"]]
            # Каждый раз выбираем 3-4 упражнения (чередуем)
            chunk_size = 3 + (si % 2)  # 3 или 4
            start_idx = (si * 2) % len(ex_names)
            today_exs = (ex_names * 3)[start_idx:start_idx + chunk_size]

            je = JournalEntry(
                created_at=session_date + timedelta(hours=1),
                slot_time=session_date,
                clients=client.fio(),
                comments=f"Тренировка #{si + 1}\n" +
                         "\n".join(f"- {ex}" for ex in today_exs),
            )
            db.add(je)

        db.commit()

        # ---- Антропометрия: замеры каждые ~2 недели (5 замеров за 2 месяца) ----
        anthro = ANTHRO.get(client_id)
        if anthro:
            # Очищаем старые замеры
            db.query(AnthropometryLog).filter(
                AnthropometryLog.client_id == client_id
            ).delete()
            db.commit()

            s_w, s_bf, s_waist, s_chest, s_shoulders, s_biceps, s_hip, s_neck, s_sf1, s_sf2, s_sf3, s_sf4, s_sf5 = anthro["start"]
            e_w, e_bf, e_waist, e_chest, e_shoulders, e_biceps, e_hip, e_neck, e_sf1, e_sf2, e_sf3, e_sf4, e_sf5 = anthro["end"]

            # 5 замеров: начальный, через 2, 4, 6, 8 недель
            measure_weeks = [0, 2, 4, 6, 8]
            for mw in measure_weeks:
                progress = mw / 8.0
                meas_date = session_dates[0] + timedelta(weeks=mw) if session_dates else now

                def _lerp(a, b):
                    return round(a + (b - a) * progress)

                log = AnthropometryLog(
                    client_id=client_id,
                    created_at=meas_date,
                    weight_kg=_lerp(s_w, e_w),
                    body_fat=_lerp(s_bf, e_bf),
                    waist_cm=_lerp(s_waist, e_waist),
                    chest_cm=_lerp(s_chest, e_chest),
                    shoulders_cm=_lerp(s_shoulders, e_shoulders),
                    biceps_cm=_lerp(s_biceps, e_biceps),
                    hip_cm=_lerp(s_hip, e_hip),
                    neck_cm=_lerp(s_neck, e_neck),
                    skinfold_chest=_lerp(s_sf1, e_sf1),
                    skinfold_abdominal=_lerp(s_sf2, e_sf2),
                    skinfold_thigh=_lerp(s_sf3, e_sf3),
                    skinfold_triceps=_lerp(s_sf4, e_sf4),
                    skinfold_subscapular=_lerp(s_sf5, e_sf5),
                )
                db.add(log)
            db.commit()
            print(f"  → Антропометрия: {anthro['start']} → {anthro['end']} (за 8 нед)")

        print(f"  → Создано {len(session_dates)} тренировок, "
              f"{db.query(ClientExerciseLog).filter(ClientExerciseLog.client_id == client_id).count()} подходов")

    db.close()
    print("\n✅ Готово! Откройте /profile под клиентом и смотрите графики.")


if __name__ == "__main__":
    seed_history()
