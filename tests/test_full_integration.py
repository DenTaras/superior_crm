"""Интеграционный тест: полный цикл для всех комбинаций абонементов.

Клиент покупает по 1 занятию каждой комбинации (3 time_slot × 3 format),
в течение недели использует их, делая жим штанги с прогрессией веса,
и в личном кабинете видит рост силовых показателей.
"""

from datetime import datetime, timedelta


def test_full_cycle_all_combos_with_progression(client, anon_client, db_session):
    """Полный цикл: покупка → бронь → тренировка → прогресс в профиле."""
    from app.models import Client, Slot, Booking, SubscriptionPurchase, Exercise, TrainingPlanExercise, ClientExerciseLog
    from app.pricing import get_price, slot_time_slot, format_from_capacity
    from app.strength import epley_1rm
    from app.auth import hash_password

    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # ---- 1. Создаём клиента с весом для нормативов ----
    c = Client(
        first_name="FullCycle", last_name="Test",
        phone="+79990000999", weight_kg=80,
        login="fullcycle", password_hash=hash_password("pass"),
    )
    db_session.add(c)
    db_session.commit()
    client_id = c.id

    # ---- 2. Покупаем по 1 занятию каждой комбинации (9 шт) ----
    combos = [
        ("УТРО", "VIP"), ("УТРО", "Double"), ("УТРО", "Group"),
        ("ДЕНЬ", "VIP"), ("ДЕНЬ", "Double"), ("ДЕНЬ", "Group"),
        ("ВЕЧЕР", "VIP"), ("ВЕЧЕР", "Double"), ("ВЕЧЕР", "Group"),
    ]
    fmt_to_cap = {"VIP": 1, "Double": 2, "Group": 4}

    for ts, fmt in combos:
        price = get_price(ts, fmt, 1)
        db_session.add(SubscriptionPurchase(
            client_id=client_id, time_slot=ts, format_name=fmt,
            package_size=1, price=price, remaining=1,
        ))
    db_session.commit()

    # ---- 3. Создаём 9 слотов через день, каждый со своим time_slot/format ----
    # Распределяем по дням: УТРО→день1, ДЕНЬ→день3, ВЕЧЕР→день5
    # По 3 слота на time_slot с шагом 1 час
    slot_defs = []
    hour_map = {"УТРО": (1, 8), "ДЕНЬ": (3, 13), "ВЕЧЕР": (5, 18)}
    for ts, fmt in combos:
        day_offset, base_hour = hour_map[ts]
        idx = [c for c in combos if c[0] == ts].index((ts, fmt))
        start = now + timedelta(days=day_offset, hours=base_hour + idx)
        slot_defs.append((start, fmt_to_cap[fmt], ts, fmt))

    slots = []
    for start_time, cap, ts, fmt in slot_defs:
        s = Slot(start_time=start_time, capacity=cap)
        db_session.add(s)
        db_session.flush()
        # Проверяем что time_slot и format совпадают
        assert slot_time_slot(s.start_time) == ts, (
            f"{s.start_time} → {slot_time_slot(s.start_time)}, expected {ts}"
        )
        assert format_from_capacity(s.capacity) == fmt, (
            f"cap={s.capacity} → {format_from_capacity(s.capacity)}, expected {fmt}"
        )
        slots.append(s)
    db_session.commit()

    assert len(slots) == 9

    # ---- 4. Берём упражнение "Жим штанги лёжа" ----
    bench_ex = db_session.query(Exercise).filter(Exercise.name == "Жим штанги лёжа").first()
    assert bench_ex is not None, "Exercise 'Жим штанги лёжа' not found"

    # ---- 5. Для каждого слота: бронь → план упражнения → завершение ----
    weights = [50, 55, 60, 65, 70, 75, 80, 85, 90]  # прогрессия 5 кг
    reps = 10  # одинаковое количество повторений
    sets = 3

    for i, s in enumerate(slots):
        slot_id = s.id
        w = weights[i]

        # 5a. Бронируем
        r = client.post(f"/slot/{slot_id}/add", data={"client_id": client_id}, follow_redirects=False)
        assert r.status_code == 303, f"Booking failed for slot {slot_id} (combo {combos[i]}), got {r.status_code}"
        loc = r.headers.get("location", "")
        assert "flash" not in loc, f"Booking rejected with flash for slot {slot_id}: {loc}"

        # 5b. Добавляем упражнение в план
        r = client.post("/api/plan-exercises/add", json={
            "slot_id": slot_id,
            "client_id": client_id,
            "exercise_id": bench_ex.id,
            "weight": w,
            "target_reps": reps,
            "sets": sets,
        })
        assert r.status_code == 200, f"Plan exercise add failed: {r.text}"
        plan_id = r.json()["id"]

        # 5c. Заполняем фактические повторения
        r = client.post("/api/plan-exercises/update", json={
            "id": plan_id,
            "actual_reps": reps,
        })
        assert r.status_code == 200, f"Plan exercise update failed: {r.text}"

        # 5d. Завершаем тренировку
        r = client.post(f"/slot/{slot_id}/complete", data={"week_offset": 0}, follow_redirects=False)
        assert r.status_code == 303, f"Complete failed for slot {slot_id}, got {r.status_code}"

    # ---- 6. Проверяем что все занятия списаны ----
    purchases = db_session.query(SubscriptionPurchase).filter(
        SubscriptionPurchase.client_id == client_id,
    ).all()
    for p in purchases:
        assert p.remaining == 0, (
            f"Purchase {p.id} ({p.time_slot}/{p.format_name}) "
            f"still has remaining={p.remaining}"
        )

    # ---- 7. Проверяем лог упражнений: 9 записей с прогрессией ----
    logs = db_session.query(ClientExerciseLog).filter(
        ClientExerciseLog.client_id == client_id,
        ClientExerciseLog.exercise_id == bench_ex.id,
    ).order_by(ClientExerciseLog.created_at.asc()).all()
    assert len(logs) == 9, f"Expected 9 log entries, got {len(logs)}"

    for i, log in enumerate(logs):
        assert log.weight == weights[i], (
            f"Log {i}: expected weight {weights[i]}, got {log.weight}"
        )
        assert log.reps == reps
        assert log.sets == sets

    # ---- 8. Проверяем профиль клиента: отображение силовых показателей ----
    # Логинимся как клиент
    anon_client.post("/login", data={"login": "fullcycle", "password": "pass"}, follow_redirects=False)
    r = anon_client.get("/profile")
    assert r.status_code == 200
    assert "Силовые показатели" in r.text, (
        f"Expected 'Силовые показатели' in profile, got: {r.text[:500]}..."
    )

    # Последний 1ПМ для жима лёжа: 90 кг × 10 повторений
    expected_1rm = epley_1rm(weights[-1], reps)
    assert str(expected_1rm) in r.text, (
        f"Expected 1RM {expected_1rm} (90×10) in profile, not found. "
        f"Profile text: {r.text[:1000]}"
    )

    # Проверяем что в профиле есть упоминание последнего лога
    assert f"{weights[-1]} кг" in r.text, (
        f"Expected weight {weights[-1]}kg in profile text"
    )

    # ---- 9. Проверяем что более ранние веса тоже есть в истории ----
    # collect_strength_data берёт только последнюю запись,
    # поэтому в профиле только последний 1ПМ.
    # Но в логе БД должны быть все 9 — уже проверили выше.
    all_logs = db_session.query(ClientExerciseLog).filter(
        ClientExerciseLog.client_id == client_id,
    ).count()
    assert all_logs == 9, f"Expected 9 total log entries, got {all_logs}"

    # ---- 10. Проверяем прямую зависимость: ClientExerciseLog.created_at ----
    # Каждая следующая запись должна быть позже предыдущей
    timestamps = [log.created_at for log in logs]
    for i in range(1, len(timestamps)):
        assert timestamps[i] >= timestamps[i - 1], (
            f"Log {i} is before log {i-1}: {timestamps[i]} < {timestamps[i-1]}"
        )
