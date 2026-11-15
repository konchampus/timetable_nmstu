import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from .config import config
from .db import async_session_factory
from .models import AuthReplay, AuthSession, RateBucket, Settings, User, UserRevocation

UTC = timezone.utc
bearer = HTTPBearer(auto_error=False)


def now() -> datetime:
    return datetime.now(UTC)


async def rate_limit(subject: str, scope: str, limit: int, seconds: int = 60):
    # Atomic shared DB buckets: no per-process bypass or lost increments.
    slot = int(time.time()) // seconds
    key = hashlib.sha256(f"{scope}:{subject}:{slot}".encode()).hexdigest()
    async with async_session_factory() as session:
        statement = insert(RateBucket).values(key=key, count=1, expires_at=now() + timedelta(seconds=seconds * 2))
        statement = statement.on_conflict_do_update(index_elements=[RateBucket.key], set_={"count": RateBucket.count + 1}).returning(RateBucket.count)
        count = (await session.execute(statement)).scalar_one()
        await session.commit()
    if count > limit:
        raise HTTPException(429, "Слишком много запросов", headers={"Retry-After": str(seconds)})


def verify_init_data(value: str) -> tuple[dict, str, datetime]:
    if not config.bot_token:
        raise HTTPException(503, "Telegram авторизация не настроена")
    pairs = parse_qsl(value, keep_blank_values=True, strict_parsing=True)
    if len(pairs) != len(dict(pairs)):
        raise ValueError("duplicate fields")
    data = dict(pairs)
    given = data.pop("hash", "")
    # Telegram's HMAC validation excludes hash only (including signature if supplied).
    check = "\n".join(f"{key}={data[key]}" for key in sorted(data))
    secret = hmac.new(b"WebAppData", config.bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, given):
        raise ValueError("invalid hash")
    timestamp = int(data["auth_date"])
    age = time.time() - timestamp
    if age < -30 or age > config.auth_max_age:
        raise ValueError("expired auth")
    user = json.loads(data["user"])
    if not isinstance(user, dict) or type(user.get("id")) is not int or not 0 < user["id"] < 2**63:
        raise ValueError("invalid user")
    return user, hashlib.sha256(check.encode()).hexdigest(), datetime.fromtimestamp(timestamp, UTC)


def revocation_digest(user_id: int) -> str:
    return hmac.new(config.bot_token.encode(), f"deleted:{user_id}".encode(), hashlib.sha256).hexdigest()


async def exchange_init_data(value: str, request: Request) -> dict:
    # Do not trust forwarding headers unless the trusted proxy is configured by uvicorn.
    await rate_limit(request.client.host if request.client else "unknown", "auth-ip", 20)
    try:
        data, replay_digest, auth_date = verify_init_data(value)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(401, "Неверные или просроченные данные Telegram") from None
    await rate_limit(str(data["id"]), "auth-user", 10)
    token = secrets.token_urlsafe(32)
    async with async_session_factory() as session:
        revocation = await session.get(UserRevocation, revocation_digest(data["id"]))
        if revocation and auth_date <= revocation.revoked_at:
            raise HTTPException(401, "После удаления откройте приложение заново")
        replay = await session.execute(insert(AuthReplay).values(digest=replay_digest, expires_at=auth_date + timedelta(seconds=config.auth_max_age + 60)).on_conflict_do_nothing().returning(AuthReplay.digest))
        if replay.scalar_one_or_none() is None:
            raise HTTPException(401, "Данные Telegram уже использованы; откройте приложение заново")
        name = " ".join(str(data.get(k, "")) for k in ("first_name", "last_name")).strip()[:150]
        await session.execute(insert(User).values(id=data["id"], name=name, active=True).on_conflict_do_nothing())
        user = (await session.execute(select(User).where(User.id == data["id"]).with_for_update())).scalar_one()
        # Re-read after the User lock: deletion may have committed while insert waited.
        revocation = (await session.execute(select(UserRevocation).where(UserRevocation.digest == revocation_digest(data["id"])).execution_options(populate_existing=True))).scalar_one_or_none()
        if revocation and auth_date <= revocation.revoked_at:
            raise HTTPException(401, "После удаления откройте приложение заново")
        if not user.active:
            raise HTTPException(401, "Аккаунт недоступен")
        user.name = name
        # A signed Telegram field records an existing user grant; it never grants permission.
        if data.get("allows_write_to_pm") is True:
            user.bot_started = True
        await session.execute(insert(Settings).values(user_id=user.id).on_conflict_do_nothing())
        session.add(AuthSession(digest=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, expires_at=now() + timedelta(seconds=config.session_seconds)))
        await session.commit()
        return {"token": token, "user": {"id": user.id, "name": user.name, "account_generation": user.account_generation}}


async def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> User:
    if credentials is None or len(credentials.credentials) > 200:
        raise HTTPException(401, "Требуется Telegram авторизация")
    digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    async with async_session_factory() as session:
        user = (await session.execute(select(User).join(AuthSession, AuthSession.user_id == User.id).where(AuthSession.digest == digest, AuthSession.expires_at > now(), User.active.is_(True)))).scalar_one_or_none()
        if user is None:
            raise HTTPException(401, "Сессия истекла")
        user.auth_token_hash = digest
        user.auth_account_generation = user.account_generation
        session.expunge(user)
    await rate_limit(str(user.id), "api", 180)
    return user


async def lock_authenticated_user(session: AsyncSession, principal: User) -> User:
    """Fence token expiry/revocation and delete/recreate ABA under the owner lock.

    Every web service, INCLUDING protected reads, must call this before accessing
    personal rows. current_user's independent authentication is not that fence.
    """
    digest = getattr(principal, "auth_token_hash", None)
    generation = getattr(principal, "auth_account_generation", None)
    if not digest or not generation:
        raise HTTPException(401, "Требуется действующая сессия")
    user = (await session.execute(select(User).where(User.id == principal.id).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if user is None or not user.active or user.account_generation != generation:
        raise HTTPException(401, "Аккаунт или сессия изменены")
    valid = (await session.execute(select(AuthSession.digest).where(
        AuthSession.digest == digest, AuthSession.user_id == user.id,
        AuthSession.expires_at > func.clock_timestamp(),
    ))).scalar_one_or_none()
    if valid is None:
        raise HTTPException(401, "Сессия отозвана или истекла")
    user.auth_token_hash = digest
    user.auth_account_generation = generation
    return user
