"""Telegram-бот для SUPERIOR CRM.

Подключается к каналу студии, отправляет уведомления,
обрабатывает команды через webhook (POST /tg-webhook).

Переменные окружения:
  BOT_TOKEN          — токен бота от @BotFather
  BOT_CHANNEL_ID     — @username канала (например @superior_gym)
  BOT_WEBHOOK_URL    — публичный URL для webhook (https://.../tg-webhook)
"""

import os
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.types import Update, WebhookInfo

_log = logging.getLogger("superior.telegram")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_CHANNEL_ID = os.getenv("BOT_CHANNEL_ID", "")

# Router для команд
router = Router()


# ---------------------------------------------------------------------------
# Команды
# ---------------------------------------------------------------------------

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Приветствие."""
    await message.answer(
        "👋 Добро пожаловать в SUPERIOR CRM!\n\n"
        "Команды:\n"
        "/schedule — расписание на сегодня\n"
        "/help — все команды"
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Справка."""
    await message.answer(
        "📋 Доступные команды:\n\n"
        "/start — приветствие\n"
        "/help — эта справка\n"
        "/schedule — расписание на сегодня\n"
        "/channel — ссылка на канал"
    )


@router.message(Command("channel"))
async def cmd_channel(message: types.Message):
    """Ссылка на канал."""
    if BOT_CHANNEL_ID:
        await message.answer(f"📢 Наш канал: {BOT_CHANNEL_ID}")
    else:
        await message.answer("Канал не настроен.")


@router.message(Command("schedule"))
async def cmd_schedule(message: types.Message):
    """Расписание на сегодня — данные из БД."""
    from app.database import SessionLocal
    from app.models import Slot, Booking, Employee, SlotEmployee

    db = SessionLocal()
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today.replace(hour=23, minute=59)

        slots = (
            db.query(Slot)
            .filter(Slot.start_time >= today, Slot.start_time <= tomorrow)
            .order_by(Slot.start_time)
            .all()
        )

        if not slots:
            await message.answer("📭 На сегодня тренировок нет.")
            return

        lines = ["📅 *Расписание на сегодня:*\n"]
        for s in slots:
            time_str = s.start_time.strftime("%H:%M")
            booked = db.query(Booking).filter(Booking.slot_id == s.id).count()
            # Тренеры на слоте
            trainers = (
                db.query(Employee)
                .join(SlotEmployee, SlotEmployee.employee_id == Employee.id)
                .filter(SlotEmployee.slot_id == s.id)
                .all()
            )
            trainer_names = ", ".join(t.fio() for t in trainers) or "—"
            lines.append(
                f"⏰ {time_str}  ({booked}/{s.capacity})  "
                f"Тренер: {trainer_names}"
            )

        await message.answer("\n".join(lines), parse_mode="Markdown")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Функции для отправки уведомлений в канал
# ---------------------------------------------------------------------------

async def post_to_channel(text: str) -> bool:
    """Отправить сообщение в канал студии."""
    if not BOT_TOKEN or not BOT_CHANNEL_ID:
        _log.warning("BOT_TOKEN или BOT_CHANNEL_ID не настроены")
        return False

    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=BOT_CHANNEL_ID, text=text, parse_mode="Markdown")
        await bot.session.close()
        return True
    except Exception as ex:
        _log.error("Failed to post to channel: %s", ex)
        return False


async def notify_slot_created(slot_time: datetime, capacity: int, trainer_name: str = ""):
    """Уведомление о новом слоте."""
    time_str = slot_time.strftime("%d.%m %H:%M")
    text = (
        f"🆕 *Новая тренировка*\n"
        f"⏰ {time_str}\n"
        f"👥 Мест: {capacity}\n"
        f"👨‍🏫 Тренер: {trainer_name or '—'}"
    )
    await post_to_channel(text)


async def notify_booking(client_name: str, slot_time: datetime):
    """Уведомление о бронировании."""
    time_str = slot_time.strftime("%d.%m %H:%M")
    text = f"✅ *Запись* — {client_name} записался на {time_str}"
    await post_to_channel(text)


# ---------------------------------------------------------------------------
# Инициализация бота
# ---------------------------------------------------------------------------

def get_dispatcher() -> Dispatcher:
    """Создать и настроить Dispatcher."""
    dp = Dispatcher()
    dp.include_router(router)
    return dp


def get_bot() -> Bot | None:
    """Вернуть экземпляр Bot или None, если токен не задан."""
    if not BOT_TOKEN:
        return None
    return Bot(token=BOT_TOKEN)
