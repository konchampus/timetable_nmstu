"""Owner-bound navigation for timetable messages; no calendar in the Mini App required."""
import secrets
from datetime import date, timedelta
from aiogram import Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from .accounts import lock_user
from .db import async_session_factory
from .models import BotInteraction
from .security import now
from .telegram_delivery import send_document
from .telegram_schedule import documents, lessons_on
from .timetable import TZ, get_schedule

SHORT_DAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def schedule_keyboard(key: str, day: date, mode: str, text_only: bool, schedule: dict) -> InlineKeyboardMarkup:
    today = now().astimezone(TZ).date()
    def button(text: str, action: str, value: date | None = None, active: bool = False):
        data = f"sched:{key}:{action}" + (":" + value.isoformat() if value else "")
        return InlineKeyboardButton(text=text, callback_data=data, **({"style": "primary"} if active else {}))
    rows = [[button("Сегодня", "day", today, mode == "day" and day == today), button("Завтра", "day", today + timedelta(days=1), mode == "day" and day == today + timedelta(days=1)), button("Сейчас / дальше", "next", active=mode == "next")]]
    step = 7 if mode == "week" else 1
    action = "week" if mode == "week" else "day"
    rows.append([button("‹ Неделя" if mode == "week" else "‹ День", action, day - timedelta(days=step)), button("Обновить", mode if mode in ("day", "week") else "next", day if mode != "next" else None), button("Неделя ›" if mode == "week" else "День ›", action, day + timedelta(days=step))])
    monday = day - timedelta(days=day.weekday())
    weekday_buttons = [button(f"{SHORT_DAYS[index]} {target.day}", "day", target, mode == "day" and target == day) for index in range(7) for target in [monday + timedelta(days=index)]]
    rows += [weekday_buttons[:4], weekday_buttons[4:]]
    rows.append([button("Вся неделя", "week", monday, mode == "week"), button("Таблица" if text_only else "Список", "rich" if text_only else "text")])
    if mode == "day":
        rooms = "\n".join(dict.fromkeys(f'{item["number"]} пара · {item["start"]} · {item["room"]}' for item in lessons_on(schedule, day) if item.get("room")))
        if rooms and len(rooms) <= 256:
            rows.append([InlineKeyboardButton(text="Скопировать аудитории", copy_text={"text": rooms})])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_schedule(bot: Bot, user_id: int, chat_id: int, schedule: dict, *, mode: str = "day", day: date | None = None, text_only: bool = False, message_id: int | None = None, expected_key: str | None = None):
    day = day or now().astimezone(TZ).date()
    pages = documents(schedule, mode, day, now())
    key = secrets.token_hex(8)
    data = {"kind": "schedule", "entity_id": schedule["entity"]["id"], "mode": mode, "date": day.isoformat(), "text_only": text_only, "chat_id": chat_id, "message_id": message_id}
    async with async_session_factory() as session:
        await lock_user(session, user_id, trusted_bot=True)
        if expected_key is not None:
            previous = (await session.execute(select(BotInteraction).where(BotInteraction.user_id == user_id).with_for_update())).scalar_one_or_none()
            if not previous or previous.key != expected_key or previous.expires_at <= now():
                raise HTTPException(409, "Эта клавиатура уже обновилась. Используйте последнее сообщение или /today.")
        expires = now() + timedelta(minutes=30)
        await session.execute(insert(BotInteraction).values(user_id=user_id, key=key, data=data, expires_at=expires).on_conflict_do_update(index_elements=[BotInteraction.user_id], set_={"key": key, "data": data, "expires_at": expires}))
        await session.commit()
    last_id = message_id
    keyboard = schedule_keyboard(key, day, mode, text_only, schedule)
    for index, page in enumerate(pages):
        result = await send_document(bot, chat_id, page, reply_markup=keyboard if index == len(pages) - 1 else None, message_id=message_id if len(pages) == 1 else None, text_only=text_only)
        if isinstance(result, Message):
            last_id = result.message_id
    async with async_session_factory() as session:
        interaction = (await session.execute(select(BotInteraction).where(BotInteraction.user_id == user_id).with_for_update())).scalar_one_or_none()
        if interaction and interaction.key == key:
            interaction.data = {**data, "message_id": last_id}
            await session.commit()


async def navigate_schedule(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) not in (3, 4) or not isinstance(callback.message, Message):
        raise HTTPException(422, "Неверная кнопка расписания")
    _, key, action = parts[:3]
    async with async_session_factory() as session:
        interaction = await session.get(BotInteraction, callback.from_user.id)
        if not interaction or interaction.key != key or interaction.expires_at <= now():
            raise HTTPException(409, "Кнопки устарели. Откройте /today или /search заново.")
        data = dict(interaction.data)
    if data.get("kind") != "schedule" or data.get("chat_id") != callback.message.chat.id or data.get("message_id") != callback.message.message_id:
        raise HTTPException(409, "Используйте кнопки последнего сообщения расписания.")
    mode, text_only = data["mode"], bool(data.get("text_only"))
    try:
        target = date.fromisoformat(parts[3] if len(parts) == 4 else data["date"])
    except (TypeError, ValueError):
        raise HTTPException(422, "Неверная дата") from None
    if abs((target - now().astimezone(TZ).date()).days) > 370:
        raise HTTPException(422, "Откройте расписание ближе к текущей дате.")
    if action in ("day", "week"):
        if len(parts) != 4:
            raise HTTPException(422, "Не указана дата")
        mode = action
    elif action == "next":
        mode, target = "next", now().astimezone(TZ).date()
    elif action in ("text", "rich"):
        text_only = action == "text"
    else:
        raise HTTPException(422, "Неизвестное действие")
    await callback.answer("Обновляю расписание")
    schedule = await get_schedule(data["entity_id"])
    await show_schedule(callback.bot, callback.from_user.id, callback.message.chat.id, schedule, mode=mode, day=target, text_only=text_only, message_id=callback.message.message_id, expected_key=key)
