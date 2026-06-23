# База данных Superior CRM

## ER-диаграмма (text)

```
Client ──1:N──> Booking ──N:1──> Slot
  │                                 │
  ├──1:N──> SubscriptionPurchase    ├──1:N──> SlotEmployee ──N:1──> Employee
  ├──1:N──> TrainingNote            │
  ├──1:N──> ClientExerciseLog       │
  ├──1:N──> TrainingPlanExercise ◀──┘
  └──1:N──> JournalEntry (via JSON clients)

ExerciseGroup ──1:N──> Exercise ──1:N──> ClientExerciseLog
                                        ──1:N──> TrainingPlanExercise

MealTemplate ──1:N──> MealProduct ──N:1──> Product
  (62 шаблона)         (~300 связей)       (93 продукта в 14 категориях)
```

## Модели

### Client
| Поле | Тип | Описание |
|------|-----|---------|
| id | Integer PK | |
| first_name | String | |
| last_name | String | |
| patronymic | String | |
| birth_year | Integer | |
| birth_place | String | |
| phone | String | |
| name | String | legacy — полное имя одной строкой |
| height_cm | Integer | рост (см) |
| weight_kg | Integer | вес (кг) |
| body_fat | Integer | % жира |
| login | String UNIQUE | для входа |
| password_hash | String | PBKDF2-SHA256 |

### Slot
| Поле | Тип | Описание |
|------|-----|---------|
| id | Integer PK | |
| start_time | DateTime | |
| capacity | Integer | 1-4. Определяет формат: 1→VIP, 2→Double, ≥3→Group |

### Booking
| Поле | Тип | Описание |
|------|-----|---------|
| id | Integer PK | |
| client_id | Integer FK→Client | |
| slot_id | Integer FK→Slot | |
| UNIQUE(slot_id, client_id) | | защита дубликатов |

### SubscriptionPurchase
| Поле | Тип | Описание |
|------|-----|---------|
| id | Integer PK | |
| client_id | Integer FK→Client | |
| time_slot | String | УТРО/ДЕНЬ/ВЕЧЕР или "-" (пробный) |
| format_name | String | VIP/Double/Group или "-" (пробный) |
| package_size | Integer | 1/4/8/12 |
| price | Integer | цена в рублях |
| remaining | Integer | осталось занятий |
| created_at | DateTime | |

### JournalEntry
| Поле | Тип | Описание |
|------|-----|---------|
| id | Integer PK | |
| created_at | DateTime | |
| slot_time | DateTime | |
| clients | String | имена через запятую |
| comments | String | JSON: client_id → текст |

### Employee
| Поле | Тип | Описание |
|------|-----|---------|
| id | Integer PK | |
| first_name | String | |
| last_name | String | |
| patronymic | String | |
| phone | String | |
| position | String | director / trainer / admin |
| login | String UNIQUE | для входа |
| password_hash | String | PBKDF2-SHA256 |
| is_active | Boolean | уволен / активен |
| salary_type | String | fixed / hourly |
| salary_amount | Integer | оклад |
| regional_coefficient | Integer | по умолчанию 100 (для Омска — 115) |
| bonus_percent | Integer | % премии |
| dividend_percent | Integer | % дивидендов |
| created_at | DateTime | |

### SlotEmployee
| Поле | Тип | Описание |
|------|-----|---------|
| id | Integer PK | |
| slot_id | Integer FK→Slot | |
| employee_id | Integer FK→Employee | |
| assigned_at | DateTime | |

### Expense
| Поле | Тип | Описание |
|------|-----|---------|
| id | Integer PK | |
| month | String | "YYYY-MM" |
| category | String | аренда, реклама и т.д. |
| description | String | |
| amount | Integer | сумма |
| created_at | DateTime | |

### Product
| Поле | Тип | Описание |
|------|-----|---------|
| id | Integer PK | |
| name | String | название |
| category | String | категория (мясо, птица, рыба, молочка…) |
| protein | Float | белки на 100г |
| fat | Float | жиры на 100г |
| carbs | Float | углеводы на 100г |
| kcal | Float | калории на 100г |

### MealProduct
| Поле | Тип | Описание |
|------|-----|---------|
| id | Integer PK | |
| meal_id | Integer FK→MealTemplate | |
| product_id | Integer FK→Product | |
| amount_g | Integer | количество граммов |

Остальные модели: TrainingNote, TrainingRequest, ExerciseGroup, Exercise, ClientExerciseLog, TrainingPlanExercise, FoodRestriction, MealTemplate, AnthropometryLog, SubscriptionConsumption.

## Миграции (Alembic)

| Ревизия | Описание |
|---------|---------|
| `9823304de3fe` | initial |
| `5376ec12a9b0` | add client login |
| `648bdfb223f0` | add training requests |
| `99538d0a78a0` | add unique constraint booking |
| `c52f3c535515` | add anthropometry, exercises, nutrition |

## Особенности

- **SQLite**: `check_same_thread=False`, `poolclass=StaticPool`
- **PostgreSQL**: через `DATABASE_URL` env var
- **Runtime-миграции**: `database.py:ensure_client_columns()`, `ensure_employee_columns()`, `ensure_training_request_columns()` добавляют колонки на лету (для совместимости SQLite/PG)
- **Сессии**: таблица `sessions` управляется `DbSessionMiddleware`, engine задаётся через `set_session_engine()`
