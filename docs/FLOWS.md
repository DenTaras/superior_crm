# Ключевые бизнес-процессы Superior CRM

## 0. Управление сотрудниками

```
1. Создание сотрудника (POST /employees/create)
   → Employee (first_name, last_name, patronymic, phone, position,
     login, password_hash, salary_type, salary_amount,
     regional_coefficient, bonus_percent, dividend_percent)

2. Назначение тренера на слот (POST /slot/{id}/assign-trainer)
   → SlotEmployee (slot_id, employee_id)
   → Отображается на странице слота

3. Увольнение (POST /employees/{id}/toggle)
   → is_active = False
   → Сотрудник не может войти в систему

4. Вход сотрудника (POST /login)
   → Проверка: Employee.login + password_hash
   → Роль: position → (director→admin, trainer→trainer, admin→admin)
```

## 0.1. Расходы бюджета

```
GET /budget (admin)
  │
  ├── Доходная часть:
  │     Общая выручка, выручка за месяц, история покупок
  │
  └── Расходная часть (на каждого сотрудника):
        salary_base = emp.salary_amount
        salary_rk   = salary_base * (emp.regional_coefficient / 100)
        ndfl        = salary_rk * 0.13      (НДФЛ 13%)
        social      = salary_rk * 0.302     (соц.взносы 30.2%)
        total_cost  = salary_rk + social     (общая стоимость для студии)
        take_home   = salary_rk - ndfl       (на руки)
        
        УСН       = monthly_revenue * 0.06   (6% от выручки)
        Аренда    = Expense WHERE category='rent' AND month=current
        Прочие    = SUM(Expense) по остальным категориям
        
        Чистая прибыль = revenue - total_costs - usn - rent - other
        Дивиденды = net_profit * (emp.dividend_percent / 100)
```

## 0.2. Питание и список покупок

```
1. Нормализация продуктов:
   → Product (93 продукта в 14 категориях: мясо, птица, рыба,
     молочка, яйца, крупы, овощи, фрукты, масла, орехи, бобовые,
     бакалея, соусы, напитки)
   → MealProduct (~300 связей) — каждый ингредиент блюда привязан
     к конкретному продукту с весом в граммах

2. Сеед продуктов (seed_products.py):
   → Очищает все MealProduct
   → Создаёт/обновляет продукты
   → Пересоздаёт все связи

3. Список покупок (GET /profile/nutrition2):
   → Для каждого дня недельного плана собирает MealProduct
   → Группирует по категориям продуктов
   → Суммирует общий вес каждого продукта
   → Отображает с группировкой по категориям
   → Экспорт в .txt (POST /profile/nutrition2/export)
```

## 0.3. Политика конфиденциальности

```
1. При регистрации (/register) и записи (/signup):
   → Отображается чекбокс "Согласие на обработку ПД"
   → Ссылка на полный текст политики (/privacy)
   → Поле pd_consent (Boolean) + pd_consent_at (DateTime) в training_requests

2. Страница политики (GET /privacy):
   → Полный текст в соответствии с 152-ФЗ
   → Цели сбора данных, сроки хранения, права субъекта

3. Отзыв согласия (POST /profile/revoke-consent):
   → Устанавливает pd_consent = False
   → Доступен в личном кабинете
```

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

## 5. Профиль тренера

```
GET /profile (trainer)
  │
  ├── Информация о сотруднике (ФИО, должность)
  │
  └── Мои ближайшие тренировки:
        SELECT Slot.* FROM Slot
        JOIN SlotEmployee ON SlotEmployee.slot_id = Slot.id
        WHERE SlotEmployee.employee_id = ?
          AND Slot.start_time > now()
        ORDER BY Slot.start_time ASC
        → Список слотов с датой, временем и количеством клиентов
```

## 6. Конструктор упражнений

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
