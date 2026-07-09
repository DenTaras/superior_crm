"""Аутентификация и роли.

Встроенные учётные записи:
  admin / admin       — администратор (из ADMIN_LOGIN/ADMIN_PASSWORD)
  trainer / trainer   — тренер (из TRAINER_LOGIN/TRAINER_PASSWORD)
  client_1 / client_1 — клиент (логин/пароль из БД)
"""

import os
import hashlib
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db, templates
from app.models import Client, Employee
from app.ratelimit import check_rate_limit, clear_rate_limit
from app.pricing import slot_time_slot
from app.timezone import now as tz_now

router = APIRouter()

ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
TRAINER_LOGIN = os.getenv("TRAINER_LOGIN", "trainer")
TRAINER_PASSWORD = os.getenv("TRAINER_PASSWORD", "trainer")

# Параметры PBKDF2
_PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    """Хеширование пароля через PBKDF2-SHA256 с уникальной солью.

    Формат: алгоритм$итерации$соль$хеш
    """
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS)
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt}${pwd_hash.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Проверить пароль против хранимого хеша (поддерживает legacy SHA256)."""
    if stored.startswith("pbkdf2$"):
        parts = stored.split("$")
        if len(parts) != 4:
            return False
        _, iterations, salt, expected_hex = parts
        try:
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
            return actual.hex() == expected_hex
        except Exception:
            return False
    # legacy: старый формат sha256 с константной солью
    return stored == hashlib.sha256(f"superior_salt_{password}".encode()).hexdigest()


def get_current_user(request: Request) -> Optional[dict]:
    """Вернуть информацию о текущем пользователе из сессии."""
    return request.session.get("user")


def require_role(*roles: str):
    """Dependency — проверяет, что пользователь авторизован и имеет одну из ролей."""
    def dependency(request: Request):
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=303, detail="/login", headers={"Location": "/login"})
        if user.get("role") not in roles:
            raise HTTPException(status_code=303, detail="/", headers={"Location": "/"})
        return user
    return dependency


# ---- Страницы ----


@router.get("/login")
def login_page(request: Request):
    """Форма входа."""
    if get_current_user(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={})


@router.post("/login")
def login_post(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Обработка входа для всех пользователей."""
    # Rate limit: 5 попыток в минуту на логин
    allowed, remaining = check_rate_limit(f"login:{login}")
    if not allowed:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Слишком много попыток. Попробуйте через минуту."},
            status_code=429,
        )

    # Проверка по сотрудникам (админ, тренер, директор)
    employee = db.query(Employee).filter(Employee.login == login, Employee.is_active == True).first()
    if employee and employee.password_hash and verify_password(password, employee.password_hash):
        clear_rate_limit(f"login:{login}")
        request.session.regenerate_id()
        role_map = {"director": "admin", "trainer": "trainer", "admin": "admin"}
        request.session["user"] = {
            "role": role_map.get(employee.position, "trainer"),
            "name": employee.fio(),
            "employee_id": employee.id,
        }
        return RedirectResponse("/", status_code=303)

    # fallback: hardcoded admin/trainer (legacy)
    if login == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        clear_rate_limit(f"login:{login}")
        request.session.regenerate_id()
        request.session["user"] = {"role": "admin", "name": "Администратор"}
        return RedirectResponse("/", status_code=303)

    if login == TRAINER_LOGIN and password == TRAINER_PASSWORD:
        clear_rate_limit(f"login:{login}")
        request.session.regenerate_id()
        request.session["user"] = {"role": "trainer", "name": "Тренер"}
        return RedirectResponse("/", status_code=303)

    # client — проверка по БД
    client = db.query(Client).filter(Client.login == login).first()
    if client and client.password_hash and verify_password(password, client.password_hash):
        clear_rate_limit(f"login:{login}")
        request.session.regenerate_id()
        request.session["user"] = {
            "role": "client",
            "name": client.fio(),
            "client_id": client.id,
        }
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Неверный логин или пароль"},
        status_code=403,
    )


# @router.get("/register")
# def register_page(request: Request):
#     """Форма регистрации нового клиента."""
#     return templates.TemplateResponse(request=request, name="register.html", context={})


# @router.post("/register")
# def register_post(
#     request: Request,
#     login: str = Form(...),
#     password: str = Form(...),
#     first_name: str = Form(...),
#     last_name: str = Form(""),
#     phone: str = Form(""),
#     pd_consent: bool = Form(False),
#     db: Session = Depends(get_db),
# ):
#     """Регистрация нового клиента."""
#     if not pd_consent:
#         return templates.TemplateResponse(
#             request=request, name="register.html",
#             context={"error": "Необходимо согласие на обработку персональных данных"},
#             status_code=403,
#         )
# 
#     # проверяем, что логин уникален
#     existing = db.query(Client).filter(Client.login == login).first()
#     if existing:
#         return templates.TemplateResponse(
#             request=request, name="register.html",
#             context={"error": "Логин уже занят"},
#             status_code=403,
#         )
# 
#     from datetime import datetime
#     client = Client(
#         login=login,
#         password_hash=hash_password(password),
#         first_name=first_name.strip(),
#         last_name=last_name.strip(),
#         phone=phone.strip(),
#         name=f"{last_name.strip()} {first_name.strip()}".strip(),
#         pd_consent_given=True,
#         pd_consent_at=datetime.now(),
#     )
#     db.add(client)
#     db.flush()
#
#     # Пробное занятие как абонемент
#     from app.models import SubscriptionPurchase
#     purchase = SubscriptionPurchase(
#         client_id=client.id,
#         time_slot="-",
#         format_name="-",
#         # "-" — универсальный формат (подходит для любого слота)
#         package_size=1,
#         price=0,
#         remaining=1,
#     )
#     db.add(purchase)
#     db.commit()
#
#     request.session.regenerate_id()
#     request.session["user"] = {
#         "role": "client",
#         "name": client.fio(),
#         "client_id": client.id,
#     }
#     return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    """Выход."""
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/profile")
def profile_page(request: Request, db: Session = Depends(get_db), agg: str = "month"):
    """Личный кабинет."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] == "client":
        client_id = user.get("client_id")
        c = db.get(Client, client_id)
        bookings = []
        journal_entries = []
        strength_data = []
        booked_by_ts: dict[str, int] = {}
        if c:
            from app.models import Booking, Slot, JournalEntry, SubscriptionPurchase, ClientExerciseLog
            from app.pricing import format_from_capacity
            import json

            # Будущие и активные бронирования
            rows = (
                db.query(Booking, Slot)
                .join(Slot, Booking.slot_id == Slot.id)
                .filter(Booking.client_id == client_id)
                .order_by(Slot.start_time.desc())
                .all()
            )
            bookings = [{"slot_time": s.start_time, "slot_id": s.id, "slot": s} for b, s in rows]

            # Доступные для бронирования слоты (будущие, не заполненные, с подходящим пакетом)
            from sqlalchemy import func, Integer, case
            from app.pricing import slot_time_slot, format_from_capacity
            ts_hour_map = {"УТРО": (8, 12), "ДЕНЬ": (12, 17), "ВЕЧЕР": (17, 24)}
            now = tz_now()
            # Все будущие слоты
            all_future_slots = db.query(Slot).filter(Slot.start_time >= now).order_by(Slot.start_time).all()
            # ID слотов, где клиент уже забронирован
            booked_slot_ids = {b.slot_id for b, _ in rows}

            available_slots = []
            client_bookings_list = []
            for sl in all_future_slots:
                slot_ts = slot_time_slot(sl.start_time)
                slot_fmt = format_from_capacity(sl.capacity)
                # Количество броней в слоте
                booked_count = db.query(Booking).filter(Booking.slot_id == sl.id).count()
                is_booked = sl.id in booked_slot_ids
                if is_booked:
                    client_bookings_list.append({
                        "slot_id": sl.id,
                        "start_time": sl.start_time,
                        "capacity": sl.capacity,
                        "format": slot_fmt,
                        "time_slot": slot_ts,
                        "booked": booked_count,
                    })
                    continue
                # Слот полон?
                if booked_count >= sl.capacity:
                    continue
                # Есть ли у клиента подходящий пакет?
                remaining = db.query(func.coalesce(func.sum(SubscriptionPurchase.remaining), 0)).filter(
                    SubscriptionPurchase.client_id == client_id,
                    SubscriptionPurchase.time_slot.in_([slot_ts, "-"]),
                    SubscriptionPurchase.format_name.in_([slot_fmt, "-"]),
                ).scalar() or 0
                if remaining == 0:
                    continue
                # Учитываем будущие брони клиента в том же time_slot+format
                h_start, h_end = ts_hour_map.get(slot_ts, (0, 24))
                slot_fmt_filter = case(
                    (Slot.capacity == 1, "VIP"),
                    (Slot.capacity == 2, "Double"),
                    else_="Group"
                )
                fut = db.query(Booking).join(Slot, Booking.slot_id == Slot.id).filter(
                    Booking.client_id == client_id,
                    Slot.start_time >= now,
                    func.cast(func.strftime("%H", Slot.start_time), Integer).between(h_start, h_end - 1),
                    slot_fmt_filter == slot_fmt,
                ).count()
                if fut >= remaining:
                    continue
                available_slots.append({
                    "slot_id": sl.id,
                    "start_time": sl.start_time,
                    "capacity": sl.capacity,
                    "format": slot_fmt,
                    "time_slot": slot_ts,
                    "booked": booked_count,
                    "label": f"{sl.start_time.strftime('%d.%m %H:%M')} — {slot_fmt} {slot_ts} ({booked_count}/{sl.capacity})",
                })

            # История завершённых тренировок из журнала
            cid_str = str(client_id)
            c_name = c.fio()
            raw_entries = (
                db.query(JournalEntry)
                .filter(JournalEntry.clients.contains(c_name))
                .order_by(JournalEntry.created_at.desc())
                .limit(50)
                .all()
            )
            for je in raw_entries:
                plan = ""
                if je.comments:
                    try:
                        cmap = json.loads(je.comments)
                        plan = cmap.get(cid_str, "")
                    except Exception as ex:
                        import logging as _lg_auth
                        _lg_auth.getLogger("superior.request").warning("PROFILE: parse journal comments: %s", ex)
                journal_entries.append({
                    "entry": je,
                    "plan": plan,
                })

            # Силовые показатели
            from app.strength import collect_strength_data, enrich_with_rank, compute_standards_table, epley_1rm
            bw = c.weight_kg or 0
            strength_data = collect_strength_data(db, client_id)
            strength_data = enrich_with_rank(strength_data, "male", bw)
            standards_table = compute_standards_table("male", bw) if bw > 0 else []

            # Расчёт типа телосложения по обхвату запястья
            body_type = None
            if c.wrist_cm:
                w = c.wrist_cm
                if w < 18:
                    body_type = "Эктоморф"
                elif w <= 20:
                    body_type = "Мезоморф"
                else:
                    body_type = "Эндоморф"

            # Navy Method: %жира по обхватам (только для мужчин)
            navy_bf_pct = None
            if c.neck_cm and c.waist_cm and c.height_cm:
                import math
                h_inch = c.height_cm / 2.54
                neck_inch = c.neck_cm / 2.54
                waist_inch = c.waist_cm / 2.54
                navy_bf_pct = round(
                    86.010 * math.log10(waist_inch - neck_inch)
                    - 70.041 * math.log10(h_inch)
                    + 36.76,
                    1,
                )
                navy_bf_pct = max(3, min(navy_bf_pct, 50))

            # Данные для графика прогресса (все упражнения клиента)
            from app.models import Exercise as ExModel
            progress_chart = {}
            # Находим все ID упражнений, по которым есть логи
            logged_ex_ids = (
                db.query(ClientExerciseLog.exercise_id)
                .filter(ClientExerciseLog.client_id == client_id)
                .distinct()
                .all()
            )
            logged_ex_ids = [r[0] for r in logged_ex_ids]
            exercises_with_logs = (
                db.query(ExModel)
                .filter(ExModel.id.in_(logged_ex_ids))
                .order_by(ExModel.name)
                .all()
            )
            for ex in exercises_with_logs:
                logs = (
                    db.query(ClientExerciseLog)
                    .filter(
                        ClientExerciseLog.client_id == client_id,
                        ClientExerciseLog.exercise_id == ex.id,
                    )
                    .order_by(ClientExerciseLog.created_at.asc())
                    .all()
                )
                points = []
                for log in logs:
                    rm = epley_1rm(log.weight, log.reps)
                    if rm:
                        points.append({
                            "x": log.created_at.strftime("%d.%m"),
                            "y": rm,
                        })
                if len(points) >= 1:
                    progress_chart[ex.name] = points
            import json
            progress_chart_json = json.dumps(progress_chart, ensure_ascii=False)
            progress_chart_names = list(progress_chart.keys())

            # Данные для графика антропометрии
            from app.models import AnthropometryLog
            anthro_logs = (
                db.query(AnthropometryLog)
                .filter(AnthropometryLog.client_id == client_id)
                .order_by(AnthropometryLog.created_at.asc())
                .all()
            )
            anthro_chart = {}
            if anthro_logs:
                fields = [
                    ("weight_kg", "Вес"),
                    ("body_fat", "Жир"),
                    ("hip_cm", "Бедро"),
                    ("waist_cm", "Талия"), ("chest_cm", "Грудь"),
                    ("shoulders_cm", "Плечи"), ("biceps_cm", "Бицепс"),
                    ("skinfold_chest", "Складка грудь"),
                    ("skinfold_abdominal", "Складка живот"),
                    ("skinfold_thigh", "Складка бедро"),
                    ("skinfold_triceps", "Складка трицепс"),
                    ("skinfold_subscapular", "Складка под лопаткой"),
                ]
                for col, label in fields:
                    points = []
                    for log in anthro_logs:
                        val = getattr(log, col, None)
                        if val is not None:
                            points.append({
                                "x": log.created_at.strftime("%d.%m"),
                                "y": val,
                            })
                    if len(points) >= 2:
                        anthro_chart[label] = points
            anthro_chart_json = json.dumps(anthro_chart, ensure_ascii=False)
            anthro_chart_names = list(anthro_chart.keys())

            # Будущие брони по time_slot
            from app.models import Slot as SlotModel
            future_slots = (
                db.query(SlotModel)
                .join(Booking, Booking.slot_id == SlotModel.id)
                .filter(Booking.client_id == client_id, SlotModel.start_time >= now)
                .all()
            )
            for sl in future_slots:
                ts = slot_time_slot(sl.start_time)
                booked_by_ts[ts] = booked_by_ts.get(ts, 0) + 1

            # Активные абонементы
            active_purchases_raw = (
                db.query(SubscriptionPurchase)
                .filter(
                    SubscriptionPurchase.client_id == client_id,
                    SubscriptionPurchase.remaining > 0,
                )
                .order_by(SubscriptionPurchase.created_at.asc())
                .all()
            )
            grouped: dict[tuple[str, str], int] = {}
            for p in active_purchases_raw:
                key = (p.format_name, p.time_slot)
                grouped[key] = grouped.get(key, 0) + p.remaining

            active_purchases = [
                {"format_name": k[0], "time_slot": k[1], "remaining": v}
                for k, v in sorted(grouped.items())
            ]

        total_remaining = sum(p["remaining"] for p in active_purchases) if c else 0

        # Достижения
        from app.achievements import compute_achievements, get_achievements
        if c:
            compute_achievements(c.id, db)
            achievements_list = get_achievements(c.id, db)
        else:
            achievements_list = []

        # Стрик (тренировки подряд, только проведённые)
        streak = 0
        streak_discount = 0
        if c:
            from datetime import timedelta
            from app.models import FreezeLog
            # Собираем даты проведённых тренировок
            session_dates = []
            for je_dict in journal_entries:
                entry_obj = je_dict.get("entry") or je_dict.get("je")
                if entry_obj and entry_obj.created_at:
                    session_dates.append(entry_obj.created_at.date())
            session_dates.sort(reverse=True)

            # Дни заморозки (лог)
            frozen_dates = set()
            for fl in db.query(FreezeLog).filter(FreezeLog.client_id == c.id).all():
                if fl.date:
                    frozen_dates.add(fl.date.date())

            today = tz_now().date()

            def _effective_gap(d1, d2):
                """Реальный разрыв минус замороженные дни между датами."""
                if d1 <= d2:
                    return 0
                gap = (d1 - d2).days
                frozen_in_gap = sum(1 for d in range((d2 - d1).days, (d1 - d2).days)
                                    if (d1 - timedelta(days=d)) in frozen_dates) if d1 > d2 else 0
                return gap - frozen_in_gap

            if session_dates:
                gap_to_today = (today - session_dates[0]).days
                # Замороженные дни от последней тренировки до сегодня
                frozen_since_last = sum(1 for d in range(1, gap_to_today + 1)
                                        if (today - timedelta(days=d)) in frozen_dates)
                effective_gap = gap_to_today - frozen_since_last
                if effective_gap <= 7:
                    streak = 1
                    for i in range(1, len(session_dates)):
                        gap = (session_dates[i - 1] - session_dates[i]).days
                        frozen_in_gap = sum(1 for d in range(1, gap)
                                            if (session_dates[i - 1] - timedelta(days=d)) in frozen_dates)
                        if gap - frozen_in_gap <= 7:
                            streak += 1
                        else:
                            break
            # Скидка: 1% за каждые 3 тренировки, макс 20%
            streak_discount = min((streak // 3), 20)

        # Статус заморозки
        now = tz_now()
        frozen_active = c.frozen_until > now if c and c.frozen_until else False
        freeze_cd_active = c.last_freeze_cd > now if c and c.last_freeze_cd else False

        return templates.TemplateResponse(
            request=request, name="user.html",
            context={
                "user": user, "client": c,
                "bookings": bookings, "journal_entries": journal_entries,
                "strength_data": strength_data,
                "standards_table": standards_table,
                "active_purchases": active_purchases,
                "booked_by_time_slot": booked_by_ts,
                "total_remaining": total_remaining,
                "available_slots": available_slots,
                "streak": streak,
                "streak_discount": streak_discount,
                "frozen_active": frozen_active,
                "freeze_cd_active": freeze_cd_active,
                "client_bookings": client_bookings_list,
                "progress_chart_json": progress_chart_json,
                "progress_chart_names": progress_chart_names,
                "achievements": achievements_list,
                "anthro_chart_json": anthro_chart_json,
                "anthro_chart_names": anthro_chart_names,
                "navy_bf_pct": navy_bf_pct,
                "body_type": body_type,
            },
        )

    # admin / trainer
    from app.models import Client as ClientModel
    from app.models import Slot as SlotModel, JournalEntry
    total_clients = db.query(ClientModel).count()
    total_slots = db.query(SlotModel).count()
    total_journal = db.query(JournalEntry).count()

    # Ближайшие тренировки для тренера
    trainer_slots = []
    if user["role"] == "trainer" and user.get("employee_id"):
        from app.models import SlotEmployee, Booking as Bk
        se_list = db.query(SlotEmployee).filter(
            SlotEmployee.employee_id == user["employee_id"]
        ).all()
        slot_ids = [se.slot_id for se in se_list]
        if slot_ids:
            upcoming = db.query(SlotModel).filter(
                SlotModel.id.in_(slot_ids),
                SlotModel.start_time >= tz_now(),
            ).order_by(SlotModel.start_time).limit(10).all()
            for s in upcoming:
                bk_count = db.query(Bk).filter(Bk.slot_id == s.id).count()
                trainer_slots.append({
                    "slot": s,
                    "client_count": bk_count,
                })

    # dashboard/budget data for admin tab
    dashboard_data = None
    budget_data = None
    if user["role"] == "admin":
        from app.models import SubscriptionPurchase, Client as ClModel
        from app.models import SubscriptionConsumption, JournalEntry as JEntry
        from app.routes.budget import _calc_expenses
        from datetime import timedelta
        from app.timezone import now as tz_now2
        from sqlalchemy import func, extract

        now_dt = tz_now2()
        month_ago = now_dt - timedelta(days=30)

        # --- Dashboard stats ---
        ac = (
            db.query(SubscriptionPurchase.client_id)
            .filter(SubscriptionPurchase.created_at >= month_ago)
            .distinct()
            .count()
        )
        rev = (
            db.query(func.coalesce(func.sum(SubscriptionPurchase.price), 0))
            .filter(SubscriptionPurchase.created_at >= month_ago)
            .scalar()
        ) or 0
        rp = (
            db.query(SubscriptionPurchase)
            .order_by(SubscriptionPurchase.created_at.desc())
            .limit(5).all()
        )
        rl = []
        for p in rp:
            cl = db.get(ClModel, p.client_id)
            rl.append({
                "date": p.created_at,
                "client_name": cl.fio() if cl else f"#{p.client_id}",
                "label": f"{p.format_name} {p.time_slot} {p.package_size}",
                "price": p.price,
            })

        total_clients_count = db.query(ClModel).count()
        active_with_sub = (
            db.query(SubscriptionPurchase.client_id)
            .filter(SubscriptionPurchase.remaining > 0)
            .distinct()
            .count()
        )
        month_trainings = (
            db.query(JEntry)
            .filter(JEntry.created_at >= month_ago)
            .count()
        )

        # --- Chart data with aggregation ---
        if agg == "hour":
            since_db = now_dt - timedelta(days=7)
            date_parts = [
                extract("year", SubscriptionPurchase.created_at).label("year"),
                extract("month", SubscriptionPurchase.created_at).label("month"),
                extract("day", SubscriptionPurchase.created_at).label("day"),
                extract("hour", SubscriptionPurchase.created_at).label("hour"),
            ]
            group_cols = ["year", "month", "day", "hour"]
            order_cols = ["year", "month", "day", "hour"]
            db_fmt = lambda r: f"{int(r.day):02d}.{int(r.month):02d} {int(r.hour):02d}:00"
            # все 48 часов назад
            all_labels = []
            for i in range(48):
                dt = now_dt - timedelta(hours=47-i)
                all_labels.append(f"{dt.day:02d}.{dt.month:02d} {dt.hour:02d}:00")
            axis_label = "Час"
        elif agg == "day":
            since_db = now_dt - timedelta(days=90)
            date_parts = [
                extract("year", SubscriptionPurchase.created_at).label("year"),
                extract("month", SubscriptionPurchase.created_at).label("month"),
                extract("day", SubscriptionPurchase.created_at).label("day"),
            ]
            group_cols = ["year", "month", "day"]
            order_cols = ["year", "month", "day"]
            db_fmt = lambda r: f"{int(r.day):02d}.{int(r.month):02d}"
            # все 30 дней назад
            all_labels = []
            for i in range(30):
                dt = now_dt - timedelta(days=29-i)
                all_labels.append(f"{dt.day:02d}.{dt.month:02d}")
            axis_label = "День"
        else:
            since_db = now_dt - timedelta(days=365)
            date_parts = [
                extract("year", SubscriptionPurchase.created_at).label("year"),
                extract("month", SubscriptionPurchase.created_at).label("month"),
            ]
            group_cols = ["year", "month"]
            order_cols = ["year", "month"]
            db_fmt = lambda r: f"{int(r.year)}-{int(r.month):02d}"
            # последние 12 месяцев
            all_labels = []
            for i in range(12):
                m = now_dt.month - i
                y = now_dt.year
                while m < 1:
                    m += 12
                    y -= 1
                all_labels.insert(0, f"{y}-{m:02d}")
            axis_label = "Месяц"

        # запрос данных из БД
        rows = (
            db.query(*date_parts, func.sum(SubscriptionPurchase.price).label("total"))
            .filter(SubscriptionPurchase.created_at >= since_db)
            .group_by(*group_cols)
            .order_by(*order_cols)
            .all()
        )
        # строим словарь существующих данных
        rev_map = {db_fmt(r): int(r.total) for r in rows}
        # заполняем все слоты (с нулями где нет данных)
        chart_labels = all_labels
        chart_revenues = [rev_map.get(l, 0) for l in all_labels]

        # slot revenue (по тому же периоду)
        slot_rows = (
            db.query(SubscriptionPurchase.time_slot, func.sum(SubscriptionPurchase.price).label("total"))
            .filter(SubscriptionPurchase.created_at >= since_db)
            .group_by(SubscriptionPurchase.time_slot)
            .all()
        )
        slot_labels = [r.time_slot for r in slot_rows]
        slot_data = [int(r.total) for r in slot_rows]

        # format revenue
        fmt_rows = (
            db.query(SubscriptionPurchase.format_name, func.sum(SubscriptionPurchase.price).label("total"))
            .filter(SubscriptionPurchase.created_at >= since_db)
            .group_by(SubscriptionPurchase.format_name)
            .all()
        )
        fmt_labels = [r.format_name for r in fmt_rows]
        fmt_data = [int(r.total) for r in fmt_rows]

        dashboard_data = {
            "active_clients": ac,
            "month_revenue": rev,
            "recent_purchases": rl,
            "chart_labels": chart_labels,
            "chart_revenues": chart_revenues,
            "slot_labels": slot_labels,
            "slot_data": slot_data,
            "fmt_labels": fmt_labels,
            "fmt_data": fmt_data,
            "total_clients": total_clients_count,
            "active_with_sub": active_with_sub,
            "month_trainings": month_trainings,
            "current_agg": agg,
            "axis_label": axis_label,
        }

        # --- Budget data ---
        budget_data = _calc_expenses(db, rev, now_dt.strftime("%Y-%m"))

        # Additional budget revenue stats
        year = now_dt.year
        month_num = now_dt.month
        month_start = now_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_num == 12:
            month_end = month_start.replace(year=year+1, month=1)
        else:
            month_end = month_start.replace(month=month_num+1)

        purchases_all = (
            db.query(SubscriptionPurchase)
            .filter(
                SubscriptionPurchase.refunded == False,
                SubscriptionPurchase.created_at >= month_start,
                SubscriptionPurchase.created_at < month_end,
            )
            .order_by(SubscriptionPurchase.created_at.desc())
            .all()
        )
        total_earned = 0
        total_unearned = 0
        for p in purchases_all:
            if p.package_size > 0:
                used = p.package_size - p.remaining
                price_per = p.price / p.package_size
                total_earned += used * price_per
                total_unearned += p.remaining * price_per

        total_revenue = total_earned + total_unearned
        purchases_count = len(purchases_all)

        month_purchases_filtered = [p for p in purchases_all if p.created_at and p.created_at >= month_ago]
        month_revenue_val = sum(p.price for p in month_purchases_filtered) if month_purchases_filtered else 0

        refunded_purchases = (
            db.query(SubscriptionPurchase)
            .filter(SubscriptionPurchase.refunded == True)
            .all()
        )
        total_refunded = sum(p.price for p in refunded_purchases) if refunded_purchases else 0

        # purchase list with client names
        purchase_list = []
        for p in purchases_all:
            cl = db.get(ClModel, p.client_id)
            name = cl.fio() if cl else f"#{p.client_id}"
            used = p.package_size - p.remaining
            purchase_list.append({
                "created_at": p.created_at,
                "client_name": name,
                "time_slot": p.time_slot,
                "format_name": p.format_name,
                "package_size": p.package_size,
                "price": p.price,
                "remaining": p.remaining,
                "used": used,
                "earned": round(used * (p.price / p.package_size)) if p.package_size > 0 else 0,
                "unearned": round(p.remaining * (p.price / p.package_size)) if p.package_size > 0 else 0,
            })

        # consumption list
        consumptions = (
            db.query(SubscriptionConsumption)
            .filter(
                SubscriptionConsumption.created_at >= month_start,
                SubscriptionConsumption.created_at < month_end,
            )
            .order_by(SubscriptionConsumption.created_at.desc())
            .limit(50)
            .all()
        )
        consumption_list = []
        for cns in consumptions:
            cl = db.get(ClModel, cns.client_id)
            name = cl.fio() if cl else f"#{cns.client_id}"
            purchase = db.get(SubscriptionPurchase, cns.purchase_id)
            consumption_list.append({
                "created_at": cns.created_at,
                "slot_time": cns.slot_time,
                "client_name": name,
                "format_name": purchase.format_name if purchase else "?",
                "time_slot": purchase.time_slot if purchase else "?",
            })

        budget_data["revenue_stats"] = {
            "total_revenue": round(total_revenue),
            "total_earned": round(total_earned),
            "total_unearned": round(total_unearned),
            "total_refunded": total_refunded,
            "purchases_count": purchases_count,
            "month_revenue": month_revenue_val,
            "sel_year": year,
            "sel_month": month_num,
        }
        budget_data["purchases"] = purchase_list
        budget_data["consumptions"] = consumption_list

    return templates.TemplateResponse(
        request=request, name="user.html",
        context={
            "user": user,
            "total_clients": total_clients,
            "total_slots": total_slots,
            "total_journal": total_journal,
            "trainer_slots": trainer_slots,
            "streak": 0,
            "streak_discount": 0,
            "frozen_active": False,
            "freeze_cd_active": False,
            "dashboard_data": dashboard_data,
            "budget_data": budget_data,
        },
    )


@router.post("/profile/book")
def profile_book(request: Request, db: Session = Depends(get_db), slot_id: int = Form(0)):
    """Клиент бронирует слот из личного кабинета."""
    from app.models import Booking, Slot, SubscriptionPurchase
    from app.pricing import slot_time_slot, format_from_capacity
    from sqlalchemy import func, Integer, case
    from app.logging_config import audit_log

    user = get_current_user(request)
    if not user or user["role"] != "client":
        return RedirectResponse("/login", status_code=303)

    client_id = user.get("client_id")
    c = db.get(Client, client_id)
    if not slot_id:
        return RedirectResponse("/profile", status_code=303)

    # Проверка заморозки
    from app.timezone import now as tz_now
    if c and c.frozen_until and c.frozen_until > tz_now():
        return RedirectResponse("/profile?flash=Абонемент заморожен. Бронирование недоступно.", status_code=303)

    slot = db.get(Slot, slot_id)
    if not slot:
        return RedirectResponse("/profile", status_code=303)

    now = tz_now()
    if slot.start_time < now:
        return RedirectResponse("/profile", status_code=303)

    # Проверка: не забронирован ли уже
    existing = db.query(Booking).filter(Booking.slot_id == slot_id, Booking.client_id == client_id).first()
    if existing:
        return RedirectResponse("/profile", status_code=303)

    # Проверка вместимости
    booked_count = db.query(Booking).filter(Booking.slot_id == slot_id).count()
    if booked_count >= slot.capacity:
        return RedirectResponse("/profile?flash=limit_reached", status_code=303)

    # Проверка пакета
    slot_ts = slot_time_slot(slot.start_time)
    slot_fmt = format_from_capacity(slot.capacity)
    remaining = db.query(func.coalesce(func.sum(SubscriptionPurchase.remaining), 0)).filter(
        SubscriptionPurchase.client_id == client_id,
        SubscriptionPurchase.time_slot.in_([slot_ts, "-"]),
        SubscriptionPurchase.format_name.in_([slot_fmt, "-"]),
    ).scalar() or 0
    if remaining == 0:
        return RedirectResponse("/profile?flash=limit_reached", status_code=303)

    # Проверка booked_future для этого time_slot+format
    ts_hour_map = {"УТРО": (8, 12), "ДЕНЬ": (12, 17), "ВЕЧЕР": (17, 24)}
    h_start, h_end = ts_hour_map.get(slot_ts, (0, 24))
    slot_fmt_filter = case(
        (Slot.capacity == 1, "VIP"),
        (Slot.capacity == 2, "Double"),
        else_="Group"
    )
    fut = db.query(Booking).join(Slot, Booking.slot_id == Slot.id).filter(
        Booking.client_id == client_id,
        Slot.start_time >= now,
        func.cast(func.strftime("%H", Slot.start_time), Integer).between(h_start, h_end - 1),
        slot_fmt_filter == slot_fmt,
    ).count()
    if fut >= remaining:
        return RedirectResponse("/profile?flash=limit_reached", status_code=303)

    db.add(Booking(client_id=client_id, slot_id=slot_id))
    db.commit()
    audit_log("superior.audit.bookings", "ADD", client_id=client_id, slot_id=slot_id)
    return RedirectResponse("/profile", status_code=303)


@router.post("/profile/cancel")
def profile_cancel(request: Request, db: Session = Depends(get_db), slot_id: int = Form(0)):
    """Клиент отменяет свою бронь."""
    from app.models import Booking
    from app.logging_config import audit_log

    user = get_current_user(request)
    if not user or user["role"] != "client":
        return RedirectResponse("/login", status_code=303)

    if not slot_id:
        return RedirectResponse("/profile", status_code=303)

    client_id = user.get("client_id")
    db.query(Booking).filter(Booking.slot_id == slot_id, Booking.client_id == client_id).delete()
    db.commit()
    audit_log("superior.audit.bookings", "REMOVE", client_id=client_id, slot_id=slot_id)
    return RedirectResponse("/profile", status_code=303)


@router.post("/profile/revoke-consent")
def profile_revoke_consent(request: Request, db: Session = Depends(get_db)):
    """Отзыв согласия на обработку ПД."""
    from datetime import datetime

    user = get_current_user(request)
    if not user or user["role"] != "client":
        return RedirectResponse("/login", status_code=303)

    client_id = user.get("client_id")
    c = db.get(Client, client_id)
    if c:
        c.pd_consent_given = False
        c.pd_consent_at = None
        db.add(c)
        db.commit()

    return RedirectResponse("/profile", status_code=303)


@router.get("/change-password")
def change_password_page(request: Request):
    """Форма смены пароля."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="change_password.html",
        context={"error": None, "success": None},
    )


@router.post("/change-password")
def change_password_post(
    request: Request,
    db: Session = Depends(get_db),
    old_password: str = Form(...),
    new_password: str = Form(...),
    new_password2: str = Form(...),
):
    """Смена пароля для любого авторизованного пользователя."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    # Валидация
    if new_password != new_password2:
        return templates.TemplateResponse(
            request=request, name="change_password.html",
            context={"error": "Новые пароли не совпадают", "success": None},
        )
    if len(new_password) < 3:
        return templates.TemplateResponse(
            request=request, name="change_password.html",
            context={"error": "Пароль должен быть минимум 3 символа", "success": None},
        )

    role = user["role"]

    if role == "client":
        client_id = user.get("client_id")
        c = db.get(Client, client_id)
        if not c or not c.password_hash or not verify_password(old_password, c.password_hash):
            return templates.TemplateResponse(
                request=request, name="change_password.html",
                context={"error": "Неверный старый пароль", "success": None},
            )
        c.password_hash = hash_password(new_password)
        db.add(c)
        db.commit()
    elif role in ("admin", "trainer"):
        employee_id = user.get("employee_id")
        if employee_id:
            emp = db.get(Employee, employee_id)
            if emp and emp.password_hash and verify_password(old_password, emp.password_hash):
                emp.password_hash = hash_password(new_password)
                db.add(emp)
                db.commit()
            elif emp and not emp.password_hash:
                # Сотрудник без пароля (создан через seed) — разрешаем установить первый пароль
                emp.password_hash = hash_password(new_password)
                db.add(emp)
                db.commit()
            else:
                return templates.TemplateResponse(
                    request=request, name="change_password.html",
                    context={"error": "Неверный старый пароль", "success": None},
                )
        else:
            # Вошли через .env fallback — нельзя сменить пароль (нет записи в БД)
            return templates.TemplateResponse(
                request=request, name="change_password.html",
                context={"error": "Смена пароля недоступна для учётной записи из .env. Обратитесь к администратору.", "success": None},
            )
    else:
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        request=request, name="change_password.html",
        context={"error": None, "success": "Пароль успешно изменён!"},
    )
