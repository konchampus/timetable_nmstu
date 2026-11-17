"""Bounded economy policy, not bot detection. Caller must hold User -> Wallet locks."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException

LOCAL_ZONE = ZoneInfo("Asia/Yekaterinburg")
REGULAR_DAILY_LIMIT = 10
REGULAR_ATTEMPT_DAILY_LIMIT = 25
BOSS_DAILY_LIMIT = 3
SPORTS_DAILY_LIMIT = 40
CAST_COOLDOWN_SECONDS = 45


def day_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = datetime.combine(now.astimezone(LOCAL_ZONE).date(), time.min, LOCAL_ZONE)
    return start, start + timedelta(days=1)


def reject(code: str, message: str) -> None:
    raise HTTPException(status_code=429, detail={"code": code, "message": message})


def check_cast(quota, now: datetime, last_cast: datetime | None, boss_id: str | None) -> None:
    if last_cast is not None and now < last_cast + timedelta(seconds=CAST_COOLDOWN_SECONDS):
        reject("fishing_cooldown", "Между забросами нужно подождать 45 секунд")
    if boss_id is not None:
        if boss_id in quota.claimed_bosses:
            reject("boss_claimed", "Награда этого босса за сегодня уже получена")
        if quota.boss_attempts >= BOSS_DAILY_LIMIT:
            reject("boss_daily_limit", "На сегодня использованы 3 попытки встречи с боссами")
    else:
        if quota.regular_catches >= REGULAR_DAILY_LIMIT:
            reject("fishing_catch_daily_limit", "На сегодня получены 10 обычных уловов")
        if quota.regular_attempts >= REGULAR_ATTEMPT_DAILY_LIMIT:
            reject("fishing_attempt_daily_limit", "На сегодня использованы 25 обычных забросов")


def check_sport(quota) -> None:
    if quota.sport_rounds >= SPORTS_DAILY_LIMIT:
        reject("sports_daily_limit", "На сегодня использованы 40 спортивных skill-раундов")


def claim_catch(quota, boss_id: str | None, *, grandfathered: bool = False) -> None:
    if boss_id is not None:
        if boss_id in quota.claimed_bosses:
            reject("boss_claimed", "Награда этого босса за сегодня уже получена")
        quota.claimed_bosses = sorted([*quota.claimed_bosses, boss_id])
    else:
        if not grandfathered and quota.regular_catches >= REGULAR_DAILY_LIMIT:
            reject("fishing_catch_daily_limit", "На сегодня получены 10 обычных уловов; завершите ловлю после сброса квоты")
        quota.regular_catches += 1


def public_limits(quota, now: datetime, last_cast: datetime | None) -> dict:
    next_cast = last_cast + timedelta(seconds=CAST_COOLDOWN_SECONDS) if last_cast is not None else None
    return {
        "policy_version": 1,
        "regular_attempts_remaining": max(0, REGULAR_ATTEMPT_DAILY_LIMIT - quota.regular_attempts),
        "regular_catches_remaining": max(0, REGULAR_DAILY_LIMIT - quota.regular_catches),
        "boss_attempts_remaining": max(0, BOSS_DAILY_LIMIT - quota.boss_attempts),
        "sport_rounds_remaining": max(0, SPORTS_DAILY_LIMIT - quota.sport_rounds),
        "claimed_bosses": list(quota.claimed_bosses),
        "next_cast_at": next_cast.isoformat() if next_cast is not None and next_cast > now else None,
        "resets_at": day_bounds(now)[1].isoformat(), "server_now": now.isoformat(),
        "regular_daily_limit": REGULAR_DAILY_LIMIT, "regular_attempt_daily_limit": REGULAR_ATTEMPT_DAILY_LIMIT,
        "boss_daily_limit": BOSS_DAILY_LIMIT, "sports_daily_limit": SPORTS_DAILY_LIMIT,
        "cast_cooldown_seconds": CAST_COOLDOWN_SECONDS,
    }
