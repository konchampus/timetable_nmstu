"""Refresh signals only: durable cursors, short unlocked reads, no sleeping DB leases.

Admission counters are per worker; shared DB rate buckets also bound cross-worker
fan-out per account. They are not the event transport: all signals come from SQL.
"""
import asyncio
from contextlib import contextmanager
from time import monotonic
from fastapi import HTTPException
from sqlalchemy import select, func
from app.config import config
from app.db import async_session_factory
from app.models import User, AuthSession
from app.security import rate_limit
from .monopoly_models import MonopolyRoom as Room, MonopolyMember as Member

POLL_SECONDS = 18.0
POLL_INTERVAL = 0.3
_active = 0
_users = {}


@contextmanager
def poll_slot(user_id):
    # No await between check and increment: atomic within this worker's event loop.
    global _active
    total_limit = getattr(config, 'monopoly_event_max_polls', 64)
    user_limit = getattr(config, 'monopoly_event_user_polls', 2)
    if _active >= total_limit or _users.get(user_id, 0) >= user_limit:
        raise HTTPException(429, 'Слишком много ожидающих запросов', headers={'Retry-After': '2'})
    _active += 1
    _users[user_id] = _users.get(user_id, 0) + 1
    try:
        yield
    finally:
        _active -= 1
        remaining = _users[user_id] - 1
        if remaining:
            _users[user_id] = remaining
        else:
            del _users[user_id]


async def read_event_version(rid, principal):
    digest = getattr(principal, 'auth_token_hash', None)
    generation = getattr(principal, 'auth_account_generation', None)
    if not digest or not generation:
        raise HTTPException(401, 'Требуется действующая сессия')
    # One statement snapshot fences live User generation AND membership generation.
    # No ORM entities/JSON/chat are loaded; SQL NULL means no room membership.
    version = (select(Room.event_version).join(Member, Member.room_id == Room.id)
               .where(Room.id == rid, Member.user_id == User.id,
                      Member.generation == User.account_generation)
               .correlate(User).scalar_subquery())
    statement = (select(User.id, version).join(AuthSession, AuthSession.user_id == User.id)
                 .where(User.id == principal.id, User.active.is_(True),
                        User.account_generation == generation, AuthSession.digest == digest,
                        AuthSession.expires_at > func.clock_timestamp()))
    async with async_session_factory() as session:
        row = (await session.execute(statement)).one_or_none()
    # Session closed (and read transaction rolled back) before any caller sleeps.
    if row is None:
        raise HTTPException(401, 'Аккаунт или сессия изменены')
    if row[1] is None:
        raise HTTPException(403, 'Нет доступа к комнате')
    return row[1]


async def wait_for_events(rid, principal, cursor, request):
    deadline = monotonic() + POLL_SECONDS
    while True:
        if await request.is_disconnected():
            raise HTTPException(499, 'Запрос отменён')
        version = await read_event_version(rid, principal)
        if version != cursor or monotonic() >= deadline:
            # Recheck live auth/membership immediately before every normal response.
            version = await read_event_version(rid, principal)
            return {'event_version': version, 'changed': version != cursor}
        await asyncio.sleep(min(POLL_INTERVAL, max(0, deadline - monotonic())))


async def poll_events(rid, principal, cursor, request):
    with poll_slot(principal.id):
        try:
            # Also bounds pool acquisition, admission SQL and slow reads. On overload
            # fail closed, never return an un-revalidated cursor on timeout.
            async with asyncio.timeout(POLL_SECONDS + 0.5):
                await rate_limit(str(principal.id), 'monopoly-events',
                                 getattr(config, 'monopoly_event_requests_per_minute', 60))
                return await wait_for_events(rid, principal, cursor, request)
        except TimeoutError:
            raise HTTPException(503, 'Сервис событий занят', headers={'Retry-After': '2'}) from None
