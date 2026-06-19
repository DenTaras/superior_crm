# Ключевые бизнес-процессы Superior CRM

## 1. Полный цикл: клиент → тренировка → журнал

```
1. Создание клиента (POST /clients/create)
   → Client + SubscriptionPurchase (format_name="-", time_slot="-", remaining=1)
   → Пробное занятие

2. Покупка абонемента (POST /clients/add_subscription)
   → SubscriptionPurchase (time_slot, format_name, package_size, price, remaining=package_size)
   → Цена из pricing.py

3. Создание слота (POST /slots/add)
   → Slot (start_time, capacity)
   → Проверка: время не в прошлом, нет пересечений

4. Бронирование (POST /slot/{id}/add)
   → Проверка: роль admin/trainer
   → Проверка: remaining > 0 для (time_slot, format_name) или wildcard ("-")
   → Проверка: booked_future < remaining (с учётом time_slot + format)
   → Проверка: вместимость слота (capacity)
   → Защита: select_for_update + retry при IntegrityError

5. Тренировка (GET /slot/{id}/program)
   → Заметки (TrainingNote) — автосохранение
   → Конструктор упражнений (TrainingPlanExercise)
   → Таблица подходов с actual_reps

6. Завершение (POST /slot/{id}/complete)
   → Списание: FIFO по (time_slot, format_name) из SubscriptionPurchase
   → Перенос actual_reps → ClientExerciseLog
   → JournalEntry (clients, comments как JSON)
   → Удаление: Slot, Booking, TrainingNote

7. Журнал (GET /journal)
   → Отображение проведённых тренировок с планом
```

## 2. Проверка прав при бронировании (подробно)

```
POST /slot/{id}/add
  │
  ├── require_role("admin", "trainer")
  │     └── нет → 303 /login
  │
  ├── Slot exists? with_for_update()
  │     └── нет → 303 /schedule
  │
  ├── Client exists?
  │     └── нет → 303 /slot/{id}?flash=limit_reached
  │
  ├── Расчёт remaining:
  │     time_slot = slot_time_slot(slot.start_time)  → УТРО/ДЕНЬ/ВЕЧЕР
  │     format    = format_from_capacity(slot.capacity) → VIP/Double/Group
  │     remaining = SUM(SubscriptionPurchase.remaining)
  │       WHERE client_id = ?
  │         AND time_slot IN (time_slot, "-")
  │         AND format_name IN (format, "-")
  │     Если remaining == 0 → 303 flash=limit_reached
  │
  ├── Расчёт booked_future:
  │     Будущие брони клиента в том же time_slot и формате
  │     Если booked_future >= remaining → 303 flash=limit_reached
  │
  ├── Дубликат?
  │     └── да → 303 /slot/{id}
  │
  ├── Вместимость?
  │     └── заполнен → 303 /slot/{id}
  │
  └── ✅ Booking создан → 303 /slot/{id}
```

## 3. Списание при завершении тренировки

```
Для каждого клиента в слоте:
  1. slot_ts = slot_time_slot(slot.start_time)
  2. slot_fmt = format_from_capacity(slot.capacity)
  3. Ищем SubscriptionPurchase:
       client_id = c.id
       time_slot IN (slot_ts, "-")
       format_name IN (slot_fmt, "-")
       remaining > 0
     ORDER BY created_at ASC  → FIFO
  4. Если найден → remaining -= 1
  5. Если не найден → списание не происходит (ошибка не вызывается)
```

## 4. Time-slot / Format matching

```
capacity → format:
  1 → VIP
  2 → Double
  ≥3 → Group

hour → time_slot:
  08:00-11:59 → УТРО
  12:00-16:59 → ДЕНЬ
  17:00-23:59 → ВЕЧЕР

wildcard:
  time_slot = "-" — подходит для любого временного слота
  format_name = "-" — подходит для любого формата
  (используется для "Пробный" абонемент)
```

## 5. Конструктор упражнений

```
1. Выбор группы мышц → GET /api/exercise-groups
2. Выбор упражнения → GET /api/exercises?group_id=N
3. Автозаполнение → GET /api/exercise-log?client_id=N&exercise_id=M
   → последний вес × 1.05 (прогрессия +5%)
4. Добавление → POST /api/plan-exercises (exercise_id, weight, reps, sets)
5. Факт → POST /api/plan-exercises/update (id, actual_reps)
6. Перенос → кнопка "Перенести из таблицы" → формирует текст заметки
7. При завершении → actual_reps копируются в ClientExerciseLog
```
