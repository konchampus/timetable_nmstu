"""Run separately: python -m app.worker. Multiple worker replicas are supported."""
import asyncio
import logging
from datetime import timedelta
from aiogram import Bot
from fastapi import HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import SQLAlchemyError
from .config import config
from .db import async_session_factory, engine
from .models import AuthReplay, AuthSession, Entity, NotificationJob, RateBucket, SearchCache, Settings, Snapshot, User, UserRevocation, BotInteraction, SnapshotArchive
from .notifications import claim_job, deliver, plan_user
from .security import now
from .timetable import get_schedule

log = logging.getLogger(__name__)


async def refresh_loop():
    while True:
        try:
            async with async_session_factory() as session:
                homes = select(Settings.preferences["home_entity"].astext).join(User, User.id == Settings.user_id).where(User.active.is_(True))
                ids = (await session.execute(select(Entity.id).outerjoin(Snapshot, Snapshot.entity_id == Entity.id).where(
                    or_(Entity.id.in_(homes), Entity.requested_at > now() - timedelta(days=1)),
                    or_(Snapshot.fetched_at.is_(None), Snapshot.fetched_at < now() - timedelta(seconds=config.source_ttl_seconds)),
                    or_(Entity.refresh_until.is_(None), Entity.refresh_until < now()),
                ).order_by(Snapshot.fetched_at.asc().nullsfirst(), Entity.id).limit(5))).scalars().all()
            for slug in ids:
                try:
                    await get_schedule(slug, mark_requested=False)
                except HTTPException:
                    log.warning("Timetable refresh unavailable")
        except SQLAlchemyError as exc:
            log.error("Refresh storage failure (%s)", type(exc).__name__)
        await asyncio.sleep(config.worker_interval_seconds)


async def planning_loop():
    cursor = 0
    while True:
        ids = []
        try:
            async with async_session_factory() as session:
                ids = (await session.execute(select(User.id).where(User.active.is_(True), User.bot_started.is_(True), User.bot_blocked.is_(False), User.id > cursor).order_by(User.id).limit(100))).scalars().all()
            if not ids:
                cursor = 0
            for user_id in ids:
                try:
                    await plan_user(user_id)
                except SQLAlchemyError as exc:
                    log.error("Planning transaction failed (%s)", type(exc).__name__)
                cursor = user_id
        except SQLAlchemyError as exc:
            log.error("Planner storage failure (%s)", type(exc).__name__)
        await asyncio.sleep(1 if len(ids) == 100 else config.worker_interval_seconds)


async def delivery_loop(bot: Bot):
    while True:
        try:
            claim = await claim_job()
            if claim:
                await deliver(bot, *claim)
                await asyncio.sleep(0.06)
            else:
                await asyncio.sleep(1)
        except SQLAlchemyError as exc:
            log.error("Delivery storage failure (%s)", type(exc).__name__)
            await asyncio.sleep(3)


async def retention_loop():
    while True:
        try:
            async with async_session_factory() as session:
                for model, column in ((AuthReplay, AuthReplay.expires_at), (AuthSession, AuthSession.expires_at), (RateBucket, RateBucket.expires_at), (SearchCache, SearchCache.expires_at), (UserRevocation, UserRevocation.expires_at), (BotInteraction, BotInteraction.expires_at)):
                    await session.execute(delete(model).where(column < now() - timedelta(hours=1)))
                await session.execute(delete(SnapshotArchive).where(SnapshotArchive.fetched_at < now() - timedelta(days=30)))
                await session.execute(delete(NotificationJob).where(NotificationJob.created_at < now() - timedelta(days=30), NotificationJob.status.not_in(["pending", "claimed", "sending"])))
                await session.commit()
        except SQLAlchemyError as exc:
            log.error("Retention storage failure (%s)", type(exc).__name__)
        await asyncio.sleep(3600)


async def main():
    if not config.bot_token:
        raise RuntimeError("BOT_TOKEN required for worker")
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    bot = Bot(config.bot_token)
    try:
        async with asyncio.TaskGroup() as group:
            group.create_task(refresh_loop())
            group.create_task(planning_loop())
            group.create_task(delivery_loop(bot))
            group.create_task(retention_loop())
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
