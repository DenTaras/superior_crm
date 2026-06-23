# Маршруты Superior CRM

## Легенда
- 🛡️ admin — только администратор
- 👥 admin/trainer — администратор и тренер
- 🔓 все — любая роль (включая анонимов с ограничениями)

## Аутентификация и профиль

| Метод | Путь | Роль | Шаблон | Описание |
|-------|------|------|--------|----------|
| GET | `/login` | 🔓 все | login.html | Форма входа |
| POST | `/login` | 🔓 все | — | Обработка входа |
| POST | `/logout` | 🔓 все | — | Выход, очистка сессии |
| GET | `/register` | 🔓 все | register.html | Форма регистрации |
| POST | `/register` | 🔓 все | — | Регистрация нового клиента |
| GET | `/profile` | 🔓 все | user.html | Личный кабинет (разный для ролей) |
| POST | `/profile/revoke-consent` | 🔓 все | — | Отзыв согласия на обработку ПД |

## Расписание и слоты

| Метод | Путь | Роль | Шаблон | Описание |
|-------|------|------|--------|----------|
| GET | `/schedule` | 🔓 все | schedule.html | Недельный календарь 08-22 |
| POST | `/slots/add` | 👥 | — | Создать слот(ы) по интервалу |
| POST | `/slots/remove` | 👥 | — | Массовое удаление слотов |
| POST | `/slots/edit/{id}` | 👥 | — | Изменить время/вместимость |
| POST | `/slots/delete/{id}` | 👥 | — | Удалить слот + брони + заметки |
| GET | `/slot/{id}` | 🔓 все | slot.html | Страница слота |
| POST | `/slot/{id}/add` | 👥 | — | Добавить бронь |
| POST | `/slot/{id}/remove` | 👥 | — | Удалить бронь |
| POST | `/slot/{id}/complete` | 👥 | — | Завершить тренировку |
| POST | `/slot/{id}/assign-trainer` | 👥 | — | Назначить тренера на слот |
| POST | `/slot/{id}/remove-trainer` | 👥 | — | Удалить тренера со слота |
| GET | `/slot/{id}/program` | 👥 | slot_program.html | План тренировки |
| POST | `/slot/{id}/program/save` | 👥 | JSON | Сохранить заметку (автосохранение) |

## Клиенты и подписки

| Метод | Путь | Роль | Шаблон | Описание |
|-------|------|------|--------|----------|
| GET | `/clients` | 👥 | clients.html | Список + пагинация + фильтр |
| GET | `/clients/create` | 👥 | clients_create.html | Форма создания |
| POST | `/clients/create` | 👥 | — | Создать клиента |
| GET | `/clients/edit/{id}` | 👥 | clients_edit.html | Форма редактирования |
| POST | `/clients/edit/{id}` | 👥 | — | Обновить клиента |
| POST | `/clients/delete/{id}` | 👥 | — | Удалить клиента |
| POST | `/clients/add_subscription` | 👥 | — | Добавить абонемент |

## Остальные

| Метод | Путь | Роль | Шаблон | Описание |
|-------|------|------|--------|----------|
| GET | `/journal` | 👥 | journal.html | Журнал тренировок |
| GET | `/dashboard` | 👥 | dashboard.html | Дашборд с графиками (Chart.js) |
| GET | `/budget` | 🛡️ | budget.html | Финансовая статистика + расходы (ФОТ, налоги) |
| GET | `/employees` | 🛡️ | employees.html | Список сотрудников |
| GET | `/employees/create` | 🛡️ | employee_form.html | Форма создания сотрудника |
| POST | `/employees/create` | 🛡️ | — | Создать сотрудника |
| GET | `/employees/{id}/edit` | 🛡️ | employee_form.html | Форма редактирования |
| POST | `/employees/{id}/edit` | 🛡️ | — | Сохранить сотрудника |
| POST | `/employees/{id}/toggle` | 🛡️ | — | Уволить / восстановить |
| GET | `/sql` | 🛡️ | sql.html | SQL-консоль |
| POST | `/sql` | 🛡️ | sql.html | Выполнить SQL |
| GET | `/subscriptions` | 🔓 все | subscriptions.html | Матрица цен |
| GET | `/signup` | 🔓 все | signup.html | Заявка на пробную (с согласием ПД) |
| POST | `/signup` | 🔓 все | — | Отправить заявку |
| GET | `/contacts` | 🔓 все | contacts.html | Контакты студии |
| GET | `/privacy` | 🔓 все | privacy.html | Политика конфиденциальности |
| GET | `/profile/nutrition` | 🛡️ client | nutrition.html | Питание v1 (карточки блюд) |
| POST | `/profile/nutrition` | 🛡️ client | — | Настройки питания / замена блюда |
| GET | `/profile/nutrition2` | 🛡️ client | nutrition2.html | Питание v2 (список покупок) |
| GET | `/api/exercise-groups` | 👥 | JSON | Список групп упражнений |
| GET | `/api/exercises` | 👥 | JSON | Упражнения по группе |
| GET | `/api/exercise-log` | 👥 | JSON | Последний лог +5% прогрессия |
| GET | `/api/plan-exercises` | 👥 | JSON | План упражнений для слота+клиента |
| POST | `/api/plan-exercises` | 👥 | JSON | Создать запись в плане |
| POST | `/api/plan-exercises/update` | 👥 | JSON | Обновить actual_reps |
| POST | `/api/plan-exercises/delete/{id}` | 👥 | JSON | Удалить из плана |

## Flash-параметры

| Параметр | Где | Сообщение |
|----------|-----|-----------|
| `flash=slot_conflict` | /schedule | Время пересекается с существующим слотом |
| `flash=limit_reached` | /schedule, /slot | У клиента нет доступных занятий |
| `flash=slot_past` | /schedule | Нельзя создать/переместить слот в прошлое |
| `flash=slot_cleared` | /schedule | Время/вместимость изменены, брони очищены |
| `flash=limit_reached` | любая | Лимит попыток входа (login) |

## Параметры query string

- `?week_offset=N` — смещение недели в календаре
- `?q_name=...` — фильтр клиентов по ФИО
- `?q_phone=...` — фильтр клиентов по телефону
- `?page=N` — пагинация клиентов
- `?agg=month|day|hour` — агрегация на дашборде
- `?flash_seconds=N` — кастомное время автозакрытия flash
