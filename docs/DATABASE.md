# База данных Superior CRM

## ER-диаграмма (text)

```
Client ──1:N──> Booking ──N:1──> Slot
  │                                 │
  └──1:N──> SubscriptionPurchase    │
  └──1:N──> TrainingNote            │
  └──1:N──> ClientExerciseLog        │
  └──1:N──> TrainingPlanExercise ───┘
  └──1:N──> JournalEntry (via JSON clients)

ExerciseGroup ──1:N──> Exercise ──1:N──> ClientExerciseLog
                                        ──1:N──> TrainingPlanExercise
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

Остальные модели: TrainingNote, TrainingRequest, ExerciseGroup, Exercise, ClientExerciseLog, TrainingPlanExercise.

## Миграции (Alembic)

| Ревизия | Описание |
|---------|---------|
| `9823304de3fe` | initial |
| `5376ec12a9b0` | add client login |
| `648bdfb223f0` | add training requests |
| `99538d0a78a0` | add unique constraint booking |

## Особенности

- **SQLite**: `check_same_thread=False`, `poolclass=StaticPool`
- **PostgreSQL**: через `DATABASE_URL` env var
- **Runtime-миграции**: `database.py:ensure_client_columns()` добавляет колонки на лету (для совместимости SQLite/PG)
- **Сессии**: таблица `sessions` управляется `DbSessionMiddleware`, engine задаётся через `set_session_engine()`
