"""Private-chat bot. One polling replica; worker/API may have multiple replicas."""
import asyncio
import logging
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, Message, WebAppInfo
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from .accounts import lock_user, read_settings, save_settings
from .config import config
from .db import async_session_factory, engine
from .models import BotInteraction, NotificationJob, Settings, Snapshot, User
from .schemas import SettingsDTO
from .security import now, rate_limit
from .timetable import TZ, get_schedule, search
from .telegram_navigation import navigate_schedule, show_schedule

router = Router()


def app_keyboard(game: str | None = None) -> InlineKeyboardMarkup:
    url = config.mini_app_url + ("?" + urlencode({"game": game}) if game else "")
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть приложение", web_app=WebAppInfo(url=url))]])


async def answer_chunks(message: Message, text: str, **kwargs):
    # Plain text avoids source/name injection; split on lines under UTF-16 limit.
    chunk = ""
    for line in text.splitlines(keepends=True):
        pieces = [line[i:i + 1500] for i in range(0, len(line), 1500)] or ["\n"]
        for piece in pieces:
            if len((chunk + piece).encode("utf-16-le")) > 7000:
                await message.answer(chunk, parse_mode=None)
                chunk = ""
            chunk += piece
    if chunk:
        await message.answer(chunk, parse_mode=None, **kwargs)


class PrivateAndSafe(BaseMiddleware):
    async def __call__(self, handler, event, data):
        message = event if isinstance(event, Message) else event.message
        sender = event.from_user
        if not isinstance(message, Message) or message.chat.type != "private" or not sender or sender.is_bot:
            return
        try:
            await rate_limit(str(sender.id), "bot", 40)
            async with async_session_factory() as session:
                # Telegram update sender is trusted only here, never in the web API.
                await session.execute(insert(User).values(id=sender.id, name=sender.full_name[:150], active=True, bot_started=True, bot_blocked=False).on_conflict_do_nothing())
                user = await lock_user(session, sender.id, trusted_bot=True)
                user.bot_started, user.bot_blocked = True, False
                await session.execute(insert(Settings).values(user_id=sender.id).on_conflict_do_nothing())
                await session.commit()
            return await handler(event, data)
        except HTTPException as exc:
            text = exc.detail if isinstance(exc.detail, str) else "Не удалось выполнить действие"
        except (ValidationError, ValueError):
            text = "Проверьте формат. /settings — справка по настройкам."
        except SQLAlchemyError as exc:
            logging.getLogger(__name__).error("Bot transaction failed (%s)", type(exc).__name__)
            text = "Хранилище временно недоступно. Повторите позже."
        if isinstance(event, CallbackQuery):
            await event.answer(text[:180], show_alert=True)
        else:
            await message.answer(text, parse_mode=None)


router.message.outer_middleware(PrivateAndSafe())
router.callback_query.outer_middleware(PrivateAndSafe())


@router.message(Command("start", "help"))
async def start(message: Message):
    await message.answer(
        "Неофициальное расписание МГТУ. Все часы — Магнитогорск (Asia/Yekaterinburg).\n"
        "/today — сегодня · /tomorrow — завтра · /week — неделя · /next — следующая пара\n"
        "/search название — группы и преподаватели; кнопкой выберите домашнюю группу\n"
        "/settings — все настройки · /mute — выключить все уведомления\n"
        "/balance — игровые очки · /leaders — рейтинг · /game fishing — открыть игру\n"
        "Расписание — двухнедельный шаблон, не местоположение преподавателя. Уведомления изначально выключены. Личные заметки и подтверждённое удаление аккаунта доступны в профиле приложения.",
        reply_markup=app_keyboard(), parse_mode=None,
    )


async def home_schedule(user_id: int) -> dict:
    async with async_session_factory() as session:
        settings = await read_settings(session, user_id)
    if not settings.home_entity:
        raise HTTPException(422, "Выберите группу: /search название")
    return await get_schedule(settings.home_entity)


@router.message(Command("today", "tomorrow", "week", "next"))
async def timetable(message: Message, command: CommandObject):
    schedule = await home_schedule(message.from_user.id)
    local = now().astimezone(TZ)
    mode = "next" if command.command == "next" else "week" if command.command == "week" else "day"
    day = local.date() + timedelta(days=1 if command.command == "tomorrow" else 0)
    await show_schedule(message.bot, message.from_user.id, message.chat.id, schedule, mode=mode, day=day, text_only=(command.args or "").strip().casefold() in ("list", "список"))


@router.callback_query(F.data.startswith("sched:"))
async def timetable_navigation(callback: CallbackQuery):
    await navigate_schedule(callback)


@router.message(Command("search"))
async def find(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("Введите /search название группы или фамилию преподавателя")
        return
    await rate_limit(str(message.from_user.id), "search", 20)
    items = (await search(command.args))[:12]
    if not items:
        await message.answer("Ничего не найдено. Уточните название или фамилию.")
        return
    key = secrets.token_hex(6)
    async with async_session_factory() as session:
        await lock_user(session, message.from_user.id, trusted_bot=True)
        await session.execute(insert(BotInteraction).values(user_id=message.from_user.id, key=key, data={"items": items}, expires_at=now() + timedelta(minutes=15)).on_conflict_do_update(index_elements=[BotInteraction.user_id], set_={"key": key, "data": {"items": items}, "expires_at": now() + timedelta(minutes=15)}))
        await session.commit()
    buttons = []
    for index, item in enumerate(items):
        row = [InlineKeyboardButton(text=item["name"], callback_data=f"view:{key}:{index}")]
        if item["kind"] == "group":
            row.append(InlineKeyboardButton(text="Моя группа", callback_data=f"home:{key}:{index}"))
        buttons.append(row)
    await message.answer("Выберите расписание. Просмотр не меняет домашнюю группу.", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.regexp(r"^(view|home):"))
async def choose(callback: CallbackQuery):
    action, key, index = callback.data.split(":")
    async with async_session_factory() as session:
        interaction = await session.get(BotInteraction, callback.from_user.id)
        if not interaction or interaction.key != key or interaction.expires_at < now():
            raise HTTPException(409, "Результаты устарели. Повторите /search")
        items = interaction.data.get("items")
        if not isinstance(items, list):
            raise HTTPException(409, "Результаты устарели. Повторите /search")
        if not index.isdigit() or int(index) >= len(items):
            raise HTTPException(422, "Неверный выбор")
        entity = items[int(index)]
        if action == "home":
            settings = await read_settings(session, callback.from_user.id)
            values = settings.model_dump()
            values.update(home_entity=entity["id"], home_name=entity["name"])
            await save_settings(session, callback.from_user.id, SettingsDTO(**values), trusted_bot=True)
    await callback.answer("Группа сохранена" if action == "home" else "Загружаю")
    schedule = await get_schedule(entity["id"])
    await show_schedule(callback.bot, callback.from_user.id, callback.message.chat.id, schedule)


SETTINGS_HELP = (
    "Все часы — Магнитогорск (UTC+05:00). Кнопки применяются сразу.\n"
    "/settings before 5,10,15,30,60 — интервалы; before off — выключить\n"
    "/settings morning HH:mm · /settings evening HH:mm — время сводок (не включает категорию)\n"
    "/settings quiet 23:00-07:00 · /settings quiet off — тихие часы\n"
    "/settings days 0,1,2,3,4,5,6 — дни отправки, 0=Пн; days off — ни одного\n"
    "/settings pause 2026-12-01T12:00:00+05:00 · /settings pause off — пауза\n"
    "/settings master on|off · morning_enabled on|off · evening_enabled on|off · changes_enabled on|off · end_enabled on|off\n"
    "/mute — отключить все проактивные сообщения. После простоя прошедшие напоминания не догоняются."
)


def settings_keyboard(settings: SettingsDTO):
    names = {"notifications_enabled": "Все уведомления", "morning_enabled": "Утро", "evening_enabled": "Вечер", "changes_enabled": "Изменения шаблона", "end_enabled": "Конец пары"}
    rows = [[InlineKeyboardButton(text=("✓ " if getattr(settings, field) else "○ ") + name, callback_data=f"toggle:{settings.version}:{field}")] for field, name in names.items()]
    rows.append([InlineKeyboardButton(text=f'{"✓" if minutes in settings.before_minutes else "○"} {minutes} мин', callback_data=f"before:{settings.version}:{minutes}") for minutes in (5, 10, 15, 30, 60)])
    rows.append([InlineKeyboardButton(text="Выключить все", callback_data=f"mute:{settings.version}:all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_settings(message: Message, user_id: int):
    async with async_session_factory() as session:
        settings = await read_settings(session, user_id)
    status = (f'Группа: {settings.home_name or "не выбрана"}\n'
              f'Уведомления: {"включены" if settings.notifications_enabled else "выключены"} · до пары: {settings.before_minutes or "выкл"}\n'
              f'Утро {settings.morning_time}: {settings.morning_enabled}; вечер {settings.evening_time}: {settings.evening_enabled}\n'
              f'Изменения: {settings.changes_enabled}; конец пары: {settings.end_enabled}\n'
              f'Дни: {settings.weekdays}; тихие часы: {settings.quiet_start or "нет"}–{settings.quiet_end or "нет"}\n'
              f'Пауза: {settings.paused_until.isoformat() if settings.paused_until else "нет"}\n\n')
    await message.answer(status + SETTINGS_HELP, reply_markup=settings_keyboard(settings), parse_mode=None)


@router.message(Command("settings"))
async def configure(message: Message, command: CommandObject):
    if command.args:
        parts = command.args.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError("setting value required")
        field, value = parts
        async with async_session_factory() as session:
            settings = await read_settings(session, message.from_user.id)
            values = settings.model_dump()
            if field == "master":
                field = "notifications_enabled"
            booleans = {"notifications_enabled", "morning_enabled", "evening_enabled", "changes_enabled", "end_enabled"}
            if field in booleans:
                if value not in ("on", "off"):
                    raise ValueError("on/off required")
                values[field] = value == "on"
                if field == "notifications_enabled" and value == "on" and not any((settings.before_minutes, settings.morning_enabled, settings.evening_enabled, settings.changes_enabled, settings.end_enabled)):
                    values["before_minutes"] = [10]
            elif field == "before":
                values["before_minutes"] = [] if value == "off" else [int(v) for v in value.split(",")]
            elif field in ("morning", "evening"):
                values[field + "_time"] = value
            elif field == "quiet":
                pair = [None, None] if value == "off" else value.split("-")
                if len(pair) != 2:
                    raise ValueError("quiet pair required")
                values["quiet_start"], values["quiet_end"] = pair
            elif field == "days":
                values["weekdays"] = [] if value == "off" else [int(v) for v in value.split(",")]
            elif field == "pause":
                values["paused_until"] = None if value == "off" else datetime.fromisoformat(value)
            else:
                raise ValueError("unknown field")
            await save_settings(session, message.from_user.id, SettingsDTO(**values), trusted_bot=True)
    await show_settings(message, message.from_user.id)


@router.message(Command("mute"))
async def mute(message: Message):
    async with async_session_factory() as session:
        settings = await read_settings(session, message.from_user.id)
        values = settings.model_dump()
        values["notifications_enabled"] = False
        await save_settings(session, message.from_user.id, SettingsDTO(**values), trusted_bot=True)
    await message.answer("Все проактивные уведомления выключены. Ответы на ваши команды остаются доступны.")


@router.callback_query(F.data.regexp(r"^(toggle|before|mute):"))
async def toggle(callback: CallbackQuery):
    action, version, field = callback.data.split(":")
    async with async_session_factory() as session:
        settings = await read_settings(session, callback.from_user.id)
        if settings.version != int(version):
            raise HTTPException(409, "Меню устарело. Откройте /settings")
        values = settings.model_dump()
        if action == "toggle" and field in {"notifications_enabled", "morning_enabled", "evening_enabled", "changes_enabled", "end_enabled"}:
            values[field] = not values[field]
            if field == "notifications_enabled" and values[field] and not any((settings.before_minutes, settings.morning_enabled, settings.evening_enabled, settings.changes_enabled, settings.end_enabled)):
                values["before_minutes"] = [10]
        elif action == "before" and int(field) in (5, 10, 15, 30, 60):
            minutes = int(field)
            values["before_minutes"] = [n for n in settings.before_minutes if n != minutes] if minutes in settings.before_minutes else settings.before_minutes + [minutes]
        elif action == "mute":
            values["notifications_enabled"] = False
        else:
            raise ValueError("invalid callback")
        await save_settings(session, callback.from_user.id, SettingsDTO(**values), trusted_bot=True)
    await callback.answer("Сохранено")
    await show_settings(callback.message, callback.from_user.id)


@router.message(Command("balance"))
async def balance(message: Message):
    from .games.models import Wallet
    async with async_session_factory() as session:
        wallet = await session.get(Wallet, message.from_user.id)
    text = f'Баланс: {wallet.balance} игровых очков.' if wallet else "Игровой кошелёк создаётся при первом открытии игр."
    await message.answer(text + " Очки не имеют денежной стоимости.", reply_markup=app_keyboard("slots"))


@router.message(Command("leaders"))
async def leaders(message: Message):
    from .games.models import Wallet
    async with async_session_factory() as session:
        rows = (await session.execute(select(Settings.nickname, Wallet.balance).join(User, User.id == Settings.user_id).join(Wallet, Wallet.user_id == User.id).where(User.active.is_(True), Settings.leaderboard_visible.is_(True)).order_by(Wallet.balance.desc(), Settings.nickname).limit(10))).all()
    text = "Публичный топ по балансу очков (не общий рейтинг состояния):\n" + ("\n".join(f'{i}. {nickname}: {score}' for i, (nickname, score) in enumerate(rows, 1)) if rows else "Участников пока нет.")
    await message.answer(text + "\nПолные рейтинги — в приложении.", reply_markup=app_keyboard("fishing"), parse_mode=None)


@router.message(Command("game"))
async def game(message: Message, command: CommandObject):
    game_id = command.args or "slots"
    if game_id not in {"slots", "fishing", "dice", "darts", "bowling", "basketball", "football", "coin", "roulette", "blackjack", "mines", "wheel"}:
        raise HTTPException(422, "Неизвестная игра")
    await message.answer("Игровые очки не имеют денежной стоимости.", reply_markup=app_keyboard(game_id))


@router.message(Command("status"))
async def status(message: Message):
    if message.from_user.id not in config.admin_ids:
        raise HTTPException(404, "Команда не найдена")
    async with async_session_factory() as session:
        queued = (await session.execute(select(func.count()).select_from(NotificationJob).where(NotificationJob.status == "pending"))).scalar_one()
        latest = (await session.execute(select(func.max(Snapshot.fetched_at)))).scalar_one()
    logging.getLogger(__name__).info("Authorized operational status requested")
    await message.answer(f'Очередь: {queued}. Последний успешный снимок: {latest or "нет"}.', parse_mode=None)


@router.errors()
async def safe_error(event):
    # Never log Telegram update bodies, tokens, source text or private messages.
    logging.getLogger(__name__).error("Bot handler failure (%s)", type(event.exception).__name__)
    return True


async def main():
    if not config.bot_token:
        raise RuntimeError("BOT_TOKEN required")
    logging.basicConfig(level=logging.WARNING)
    bot = Bot(config.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    commands = {"start": "Начать", "today": "Сегодня", "tomorrow": "Завтра", "week": "Неделя", "next": "Следующая пара", "search": "Поиск", "settings": "Уведомления", "mute": "Выключить все", "balance": "Игровые очки", "leaders": "Рейтинг", "help": "Помощь"}
    try:
        await bot.set_my_commands([BotCommand(command=k, description=v) for k, v in commands.items()])
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Расписание", web_app=WebAppInfo(url=config.mini_app_url)))
        # No delete_webhook(drop_pending_updates=True): never silently discard updates.
        await dispatcher.start_polling(bot, handle_as_tasks=False, allowed_updates=dispatcher.resolve_used_update_types(), close_bot_session=False)
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
