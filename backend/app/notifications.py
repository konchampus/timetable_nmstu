import hashlib
from datetime import date, datetime, time, timedelta
from uuid import uuid4
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter, TelegramServerError
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from .accounts import settings_dto
from .config import config
from .db import async_session_factory
from .models import Entity, NotificationCursor, NotificationJob, Settings, Snapshot, User
from .schemas import SettingsDTO
from .security import now
from .timetable import TZ, entity_dto, week_at
from .telegram_delivery import send_document
from .telegram_schedule import Section, day_label, documents, lesson_view


def day_lessons(lessons: list[dict], day: date) -> list[dict]:
    moment = datetime.combine(day, time(12), TZ)
    return sorted((item for item in lessons if item["week"] == week_at(moment) and item["weekday"] == day.weekday()), key=lambda item: (item["start"], item["number"], item["title"]))


def at(day: date, clock: str) -> datetime:
    return datetime.combine(day, time.fromisoformat(clock), TZ)


def quiet(settings: SettingsDTO, moment: datetime) -> bool:
    if settings.quiet_start is None:
        return False
    clock = moment.astimezone(TZ).strftime("%H:%M")
    start, end = settings.quiet_start, settings.quiet_end
    if start == end:
        return True
    return start <= clock < end if start < end else clock >= start or clock < end


def permitted(settings: SettingsDTO, moment: datetime) -> bool:
    local = moment.astimezone(TZ)
    return (settings.notifications_enabled and local.weekday() in settings.weekdays
            and not (settings.paused_until and settings.paused_until > moment)
            and not quiet(settings, moment))


def next_permitted(settings: SettingsDTO, moment: datetime) -> datetime | None:
    # Changes can coalesce until quiet hours end; lesson reminders never catch up.
    candidate = moment.astimezone(TZ).replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(8 * 24 * 60):
        if permitted(settings, candidate):
            return candidate
        candidate += timedelta(minutes=1)
    return None


def lesson_line(item: dict) -> str:
    teachers = ", ".join(e["name"] for e in item["teachers"])
    return f'{item["number"]}. {item["start"]}–{item["end"]} · {item["title"]} ({item["kind"]}) · {item["room"]}' + (f' · {teachers}' if teachers else '')


def summary(lessons: list[dict], day: date) -> str:
    selected = day_lessons(lessons, day)
    return f'{day:%d.%m.%Y} · расчёт по двухнедельному шаблону\n' + ("\n".join(lesson_line(item) for item in selected) if selected else "По шаблону занятий нет.")


async def enqueue(session, user: User, settings: SettingsDTO, snapshot: Snapshot, category: str, event: str, due: datetime, text: str, expires: datetime | None = None, *, presentation: list[dict] | None = None):
    if due < now() or (category != "changes" and not permitted(settings, due)):
        return
    key = hashlib.sha256(f"{user.id}:{settings.version}:{settings.home_entity}:{snapshot.content_hash}:{category}:{event}:{due.isoformat()}".encode()).hexdigest()
    pages = presentation or [None]
    if len(pages) > 1:
        previous = await session.scalar(select(NotificationJob.payload).where(NotificationJob.dedupe == key))
        if previous is not None and "document" not in previous:
            # Do not append new pages to an already queued legacy whole event.
            return
    for index, document in enumerate(pages):
        page_key = key if index == 0 else hashlib.sha256(f"{key}:page:{index}".encode()).hexdigest()
        payload = {"text": document["fallback"]["text"], "document": document} if document else {"text": text[:3400] + ("\nПолное расписание — /today или /week." if len(text) > 3400 else "")}
        await session.execute(insert(NotificationJob).values(
            id=str(uuid4()), user_id=user.id, dedupe=page_key, entity_id=settings.home_entity,
            snapshot_hash=snapshot.content_hash, settings_version=settings.version, category=category,
            payload=payload, due_at=due + timedelta(seconds=index),
            expires_at=expires or due + timedelta(seconds=90), status="pending",
        ).on_conflict_do_nothing(index_elements=[NotificationJob.dedupe]))


async def plan_user(user_id: int):
    async with async_session_factory() as session:
        user = (await session.execute(select(User).where(User.id == user_id).with_for_update())).scalar_one_or_none()
        if not user or not user.active or user.bot_blocked or not user.bot_started:
            return
        row = await session.get(Settings, user.id)
        if not row:
            return
        settings = settings_dto(row)
        if not settings.home_entity or not settings.notifications_enabled:
            return
        snapshot = await session.get(Snapshot, settings.home_entity)
        if not snapshot or (now() - snapshot.fetched_at).total_seconds() > config.source_max_age_seconds:
            return
        entity = await session.get(Entity, settings.home_entity)
        if entity is None:
            return
        schedule = {"entity": entity_dto(entity), "lessons": snapshot.lessons, "fetched_at": snapshot.fetched_at.isoformat(), "stale": False}

        def notice(title, target, items, due, *, introduction=None, following=None):
            sections = [Section(day_label(target), target, [lesson_view(item, target, schedule, due) for item in items], introduction)]
            if following is not None:
                next_day, next_items = following
                sections.append(Section("Следующая · " + day_label(next_day), next_day, [lesson_view(item, next_day, schedule, due) for item in next_items]))
            return documents(schedule, "notice", target, due, title_override=title, sections_override=sections)

        cursor = await session.get(NotificationCursor, user.id)
        if cursor is None:
            cursor = NotificationCursor(user_id=user.id, entity_id=settings.home_entity, content_hash=snapshot.content_hash, settings_version=settings.version)
            session.add(cursor)
        elif cursor.entity_id != settings.home_entity or cursor.settings_version != settings.version:
            cursor.entity_id, cursor.content_hash, cursor.settings_version = settings.home_entity, snapshot.content_hash, settings.version
        elif cursor.content_hash != snapshot.content_hash:
            if settings.changes_enabled:
                due = now() + timedelta(seconds=2) if permitted(settings, now()) else next_permitted(settings, now())
                if due:
                    # Only the latest summary survives a quiet-hours change burst.
                    await session.execute(delete(NotificationJob).where(NotificationJob.user_id == user.id, NotificationJob.category == "changes", NotificationJob.status == "pending"))
                    await enqueue(session, user, settings, snapshot, "changes", snapshot.content_hash, due,
                                  "Изменён шаблон расписания домашней группы. Это не подтверждённая замена на конкретную дату.\nОткройте /today или /week для просмотра.", due + timedelta(hours=24), presentation=notice("Расписание обновилось", due.astimezone(TZ).date(), [], due, introduction="Изменился опубликованный шаблон домашней группы. Это не подтверждённая замена на конкретную дату. Откройте /today или /week для просмотра."))
            cursor.content_hash = snapshot.content_hash
        today = now().astimezone(TZ).date()
        for day in (today, today + timedelta(days=1)):
            lessons = day_lessons(snapshot.lessons, day)
            if settings.morning_enabled:
                await enqueue(session, user, settings, snapshot, "morning", str(day), at(day, settings.morning_time), "Расписание на сегодня\n" + summary(snapshot.lessons, day), presentation=documents(schedule, "day", day, at(day, settings.morning_time), title_override="Утреннее расписание"))
            if settings.evening_enabled:
                await enqueue(session, user, settings, snapshot, "evening", str(day), at(day, settings.evening_time), "Расписание на завтра\n" + summary(snapshot.lessons, day + timedelta(days=1)), presentation=documents(schedule, "day", day + timedelta(days=1), at(day, settings.evening_time), title_override="Завтра · расписание"))
            for item in lessons:
                for minutes in settings.before_minutes:
                    start = at(day, item["start"])
                    await enqueue(session, user, settings, snapshot, "before", f'{day}:{item["id"]}:{minutes}', start - timedelta(minutes=minutes), f'Через {minutes} мин по опубликованному расписанию:\n' + lesson_line(item), min(start, start - timedelta(minutes=minutes) + timedelta(seconds=90)), presentation=notice(f"Скоро пара · через {minutes} мин", day, [item], start - timedelta(minutes=minutes)))
                if settings.end_enabled:
                    end = at(day, item["end"])
                    future = [other for other in lessons if other["start"] >= item["end"]]
                    nearest, next_day = [], day
                    if future:
                        nearest = [other for other in future if other["start"] == future[0]["start"]]
                    else:
                        for offset in range(1, 15):
                            next_day = day + timedelta(days=offset)
                            next_lessons = day_lessons(snapshot.lessons, next_day)
                            if next_lessons:
                                nearest = [other for other in next_lessons if other["start"] == next_lessons[0]["start"]]
                                break
                    next_text = "\nВ ближайшие 14 дней по шаблону занятий нет." if not nearest else f"\nСледующая · {next_day:%d.%m}:\n" + "\n".join(lesson_line(other) for other in nearest)
                    presentation = notice("Пара закончилась по шаблону", day, [item], end, introduction="После этой пары в ближайшие 14 дней по шаблону занятий нет." if not nearest else None, following=(next_day, nearest) if nearest else None)
                    await enqueue(session, user, settings, snapshot, "end", f'{day}:{item["id"]}', end, "По шаблону закончилась пара:\n" + lesson_line(item) + next_text, presentation=presentation)
        await session.commit()


async def claim_job() -> tuple[str, str] | None:
    async with async_session_factory() as session:
        # A send may have reached Telegram. Never retry an ambiguous external effect.
        await session.execute(update(NotificationJob).where(NotificationJob.status == "sending", NotificationJob.lease_until <= func.clock_timestamp()).values(status="uncertain", last_error="interrupted_send"))
        await session.execute(update(NotificationJob).where(NotificationJob.status == "claimed", NotificationJob.lease_until <= func.clock_timestamp()).values(status="pending", lease_token=None, lease_until=None))
        await session.execute(update(NotificationJob).where(NotificationJob.status == "pending", NotificationJob.expires_at <= func.clock_timestamp()).values(status="expired"))
        job = (await session.execute(select(NotificationJob).where(NotificationJob.status == "pending", NotificationJob.due_at <= func.clock_timestamp(), NotificationJob.expires_at > func.clock_timestamp()).order_by(NotificationJob.due_at).with_for_update(skip_locked=True).limit(1))).scalar_one_or_none()
        if job is None:
            await session.commit()
            return None
        token = str(uuid4())
        job.status, job.lease_token, job.lease_until = "claimed", token, func.clock_timestamp() + timedelta(seconds=60)
        result = job.id, token
        await session.commit()
        return result


async def finish(job_id: str, token: str, status: str, error: str | None = None, retry_after: int | None = None):
    async with async_session_factory() as session:
        values = {"status": status, "last_error": error, "lease_until": None}
        if retry_after is not None:
            values["due_at"] = func.clock_timestamp() + timedelta(seconds=retry_after)
        await session.execute(update(NotificationJob).where(NotificationJob.id == job_id, NotificationJob.lease_token == token, NotificationJob.status == "sending", NotificationJob.lease_until > func.clock_timestamp()).values(**values))
        await session.commit()


async def deliver(bot: Bot, job_id: str, token: str):
    async with async_session_factory() as session:
        owner_id = (await session.execute(select(NotificationJob.user_id).where(NotificationJob.id == job_id))).scalar_one_or_none()
        if owner_id is None:
            return
        # Same lock order as settings/deletion: user, settings, job. Network is outside tx.
        user = (await session.execute(select(User).where(User.id == owner_id).with_for_update())).scalar_one_or_none()
        row = await session.get(Settings, owner_id)
        job = (await session.execute(select(NotificationJob).where(NotificationJob.id == job_id).with_for_update())).scalar_one_or_none()
        checked_at = await session.scalar(select(func.clock_timestamp()))
        if not job or job.status != "claimed" or job.lease_token != token or not job.lease_until or job.lease_until <= checked_at:
            return
        valid = bool(user and user.active and user.bot_started and not user.bot_blocked and row)
        if valid:
            settings = settings_dto(row)
            snapshot = await session.get(Snapshot, job.entity_id)
            category_on = {"morning": settings.morning_enabled, "evening": settings.evening_enabled, "changes": settings.changes_enabled, "end": settings.end_enabled, "before": bool(settings.before_minutes)}.get(job.category, False)
            valid = bool(category_on and permitted(settings, checked_at) and settings.version == job.settings_version and settings.home_entity == job.entity_id and snapshot and snapshot.content_hash == job.snapshot_hash and (checked_at - snapshot.fetched_at).total_seconds() <= config.source_max_age_seconds and job.expires_at > checked_at)
        if not valid:
            job.status = "cancelled"
            await session.commit()
            return
        text, recipient, document = job.payload["text"], user.id, job.payload.get("document")
        account_generation = user.account_generation
        job.status = "sending"
        job.attempts += 1
        job.lease_until = func.clock_timestamp() + timedelta(seconds=90)
        await session.commit()
    try:
        if isinstance(document, dict) and document.get("version") == 1:
            await send_document(bot, recipient, document)
        else:
            await bot.send_message(recipient, text, parse_mode=None, request_timeout=30)
    except TelegramRetryAfter as exc:
        await finish(job_id, token, "pending", "telegram_429", max(1, exc.retry_after))
    except TelegramForbiddenError:
        async with async_session_factory() as session:
            # A late network reply belongs to this account incarnation and lease only.
            owned_send = select(NotificationJob.id).where(
                NotificationJob.id == job_id, NotificationJob.user_id == recipient,
                NotificationJob.lease_token == token, NotificationJob.status == "sending",
                NotificationJob.lease_until > func.clock_timestamp(),
            ).exists()
            await session.execute(update(User).where(
                User.id == recipient, User.account_generation == account_generation,
                User.active.is_(True), owned_send,
            ).values(bot_blocked=True))
            await session.commit()
        await finish(job_id, token, "blocked", "telegram_forbidden")
    except TelegramBadRequest:
        await finish(job_id, token, "failed", "telegram_bad_request")
    except (TelegramNetworkError, TelegramServerError, TimeoutError):
        await finish(job_id, token, "uncertain", "unknown_send_result")
    else:
        await finish(job_id, token, "sent")
