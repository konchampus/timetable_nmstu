"""Adapter for the public MAGTU source; never infers cancellations from parse failures."""
import asyncio
import hashlib
import json
import math
import re
import unicodedata
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import quote, unquote, urlsplit
from urllib.robotparser import RobotFileParser
from uuid import uuid4
from zoneinfo import ZoneInfo
import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from .config import config
from .db import async_session_factory
from .models import Entity, SearchCache, Snapshot, SnapshotArchive, SourceBudget
from .security import now

SOURCE = "https://timetable.magtu.ru"
TZ = ZoneInfo(config.timezone)


def canonical_slug(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    if not 1 <= len(value) <= 200 or value != value.strip() or value in (".", "..") or not re.fullmatch(r"[\wА-Яа-яЁё .()–—-]+", value):
        raise HTTPException(422, "Недопустимый идентификатор расписания")
    if any(char in value for char in ("/", "\\", "%", ":", "?", "#")):
        raise HTTPException(422, "Требуется относительный идентификатор")
    return value


def source_slug(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        if parts.scheme != "https" or parts.netloc != "timetable.magtu.ru":
            raise ValueError("foreign source link")
    if parts.query or parts.fragment:
        raise ValueError("unexpected link suffix")
    return canonical_slug(unquote(parts.path.removeprefix("/")))


def entity_dto(row: Entity) -> dict:
    return {"id": row.id, "name": row.name, "kind": row.kind, "url": row.url}


def week_at(value: datetime) -> int:
    # Exact source algorithm: date-only JS anchor is UTC, not local or ISO week.
    anchor = datetime(2024, 8, 19, tzinfo=timezone.utc)
    week = math.ceil((value - anchor).total_seconds() / 604800)
    return 2 if week % 2 == 0 else 1


def date_week(day: date) -> int:
    """Template parity for a calendar date, anchored at local noon (not ISO week)."""
    return week_at(datetime.combine(day, time(12), TZ))


async def reserve_request(spacing: float | None = None):
    # A DB reservation bounds aggregate traffic across API/bot/worker replicas.
    async with async_session_factory() as session:
        await session.execute(insert(SourceBudget).values(id=1, next_at=now()).on_conflict_do_nothing())
        row = (await session.execute(select(SourceBudget).where(SourceBudget.id == 1).with_for_update())).scalar_one()
        reserved = max(now(), row.next_at)
        if reserved > now() + timedelta(seconds=30):
            raise HTTPException(503, "Источник занят, повторите позже")
        row.next_at = reserved + timedelta(seconds=max(config.source_request_spacing, spacing or 0))
        await session.commit()
    delay = (reserved - now()).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)


async def robots_policy(path: str) -> float:
    async with async_session_factory() as session:
        cache = await session.get(SearchCache, "policy:robots")
        rules = cache.items[0] if cache and cache.expires_at > now() else None
    if rules is None:
        rules = await source_get("/robots.txt", check_robots=False)
        async with async_session_factory() as session:
            await session.execute(insert(SearchCache).values(query="policy:robots", items=[rules], expires_at=now() + timedelta(hours=6)).on_conflict_do_update(index_elements=[SearchCache.query], set_={"items": [rules], "expires_at": now() + timedelta(hours=6)}))
            await session.commit()
    parser = RobotFileParser(SOURCE + "/robots.txt")
    parser.parse(rules.splitlines())
    if not parser.can_fetch("MagtuCompanion", SOURCE + path):
        raise HTTPException(503, "Источник запрещает автоматическую загрузку этого раздела")
    return float(parser.crawl_delay("MagtuCompanion") or parser.crawl_delay("*") or 0)


def validate_source_request(path: str, params: dict | None) -> None:
    # This application is a finite public timetable viewer, not a URL crawler.
    # Only the website's own search endpoint and canonical timetable pages are used.
    if path == "/api/v2/search":
        if not params or set(params) != {"q"} or not isinstance(params["q"], str) or not 2 <= len(params["q"]) <= 100:
            raise HTTPException(422, "Недопустимый запрос поиска")
    elif path == "/robots.txt":
        if params:
            raise HTTPException(422, "Недопустимые параметры источника")
    else:
        if params or not path.startswith("/") or "/" in path[1:]:
            raise HTTPException(422, "Недопустимый путь источника")
        canonical_slug(unquote(path[1:]))


async def source_get(path: str, params: dict | None = None, check_robots: bool = True) -> str:
    validate_source_request(path, params)
    # robots.txt is a crawler/indexing policy, not an HTTP authorization decision.
    # Strict crawler-policy mode remains available to the deployment operator.
    # Public-viewer mode never changes identity, follows redirects or retries 403/429.
    spacing = await robots_policy(path) if check_robots and config.source_access_mode == "robots" else 0
    for attempt in range(3):
        await reserve_request(spacing)
        try:
            async with httpx.AsyncClient(timeout=config.source_timeout_seconds, follow_redirects=False, headers={"User-Agent": "MagtuCompanion/1.0 (unofficial timetable viewer)", "Accept": "text/html,application/json"}) as client:
                async with client.stream("GET", SOURCE + path, params=params) as response:
                    # Do not follow source redirects to arbitrary or protected locations.
                    if response.status_code in (403, 429) or 300 <= response.status_code < 400:
                        raise HTTPException(503, "Источник ограничил доступ")
                    if path == "/robots.txt" and response.status_code == 404:
                        return ""
                    response.raise_for_status()
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 2_000_000:
                            raise ValueError("source response too large")
                    return content.decode("utf-8-sig")
        except (httpx.HTTPError, UnicodeError, ValueError):
            if attempt == 2:
                raise HTTPException(503, "Источник расписания недоступен") from None
            await asyncio.sleep(2 ** attempt)
    raise HTTPException(503, "Источник недоступен")


async def search(query: str) -> list[dict]:
    query = " ".join(query.strip().split())
    if not 2 <= len(query) <= 100:
        raise HTTPException(422, "Введите от 2 до 100 символов")
    key = "q:" + hashlib.sha256(query.casefold().encode()).hexdigest()
    async with async_session_factory() as session:
        cache = await session.get(SearchCache, key)
        if cache and cache.expires_at > now():
            return cache.items
    # Advisory transaction locks coalesce identical searches across processes. No network
    # under locks: the cache has a short lease represented by a placeholder expiry.
    lease_key = "lease:" + hashlib.sha256(key.encode()).hexdigest()
    token = str(uuid4())
    async with async_session_factory() as session:
        statement = insert(SearchCache).values(query=lease_key, items=[token], expires_at=now() + timedelta(seconds=60))
        statement = statement.on_conflict_do_update(index_elements=[SearchCache.query], set_={"items": [token], "expires_at": now() + timedelta(seconds=60)}, where=SearchCache.expires_at < now()).returning(SearchCache.query)
        claimed = (await session.execute(statement)).scalar_one_or_none()
        await session.commit()
    if claimed is None:
        for _ in range(20):
            await asyncio.sleep(0.5)
            async with async_session_factory() as session:
                cache = await session.get(SearchCache, key)
                if cache and cache.expires_at > now():
                    return cache.items
        raise HTTPException(503, "Поиск обновляется, повторите позже")
    try:
        data = json.loads(await source_get("/api/v2/search", {"q": query}))
        if not isinstance(data, list):
            raise ValueError("invalid search schema")
        items = []
        async with async_session_factory() as session:
            # Fence publication, not just release: an expired requester must not
            # overwrite a newer replica's catalogue or cache after a slow response.
            lease = (await session.execute(select(SearchCache).where(
                SearchCache.query == lease_key,
            ).with_for_update())).scalar_one_or_none()
            checked_at = await session.scalar(select(func.clock_timestamp()))
            if not lease or lease.items != [token] or lease.expires_at <= checked_at:
                raise HTTPException(503, "Поиск обновляется, повторите запрос")
            for item in data[:100]:
                if not isinstance(item, dict):
                    raise ValueError("invalid search item")
                if item.get("type") not in ("teacher", "group"):
                    continue
                slug = source_slug(item["url"])
                name = str(item["name"]).strip()[:200]
                dto = {"id": slug, "name": name, "kind": item["type"], "url": SOURCE + "/" + quote(slug)}
                items.append(dto)
                await session.execute(insert(Entity).values(**dto, requested_at=datetime(1970, 1, 1, tzinfo=timezone.utc)).on_conflict_do_update(index_elements=[Entity.id], set_={"name": name, "kind": dto["kind"], "url": dto["url"]}))
            await session.execute(insert(SearchCache).values(query=key, items=items, expires_at=now() + timedelta(minutes=5)).on_conflict_do_update(index_elements=[SearchCache.query], set_={"items": items, "expires_at": now() + timedelta(minutes=5)}))
            await session.commit()
        return items
    except (ValueError, KeyError, TypeError):
        raise HTTPException(503, "Формат поиска источника изменился") from None
    finally:
        async with async_session_factory() as session:
            await session.execute(update(SearchCache).where(SearchCache.query == lease_key, SearchCache.items == [token]).values(expires_at=now()))
            await session.commit()


def clean(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


async def parse_schedule(html: str, entity: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select_one(".main-table-wrap") or not soup.select_one(".group-name"):
        raise ValueError("unrecognized timetable")
    weeks = soup.select(".week[id^='week-']")
    if {node.get("id") for node in weeks} != {"week-1", "week-2"}:
        raise ValueError("both weeks required")
    links: dict[tuple[str, str], dict] = {}
    lessons = []
    for week_node in weeks:
        week = int(week_node["id"].split("-")[-1])
        days = week_node.select(".day[id^='day-']")
        if not days:
            raise ValueError("missing day structure")
        for day in days:
            weekday = int(day["id"].split("-")[-1]) - 1
            if weekday not in range(7):
                raise ValueError("invalid day")
            for lesson in day.select(".less"):
                title, room = clean(lesson.select_one(".title")), clean(lesson.select_one(".aud"))
                timing = re.fullmatch(r"(\d{2}:\d{2})\s*[–—-]\s*(\d{2}:\d{2})", clean(lesson.select_one(".time")))
                number = clean(lesson.select_one(".couple-number"))
                if not title or not timing or not number.isdigit():
                    raise ValueError("incomplete lesson")
                start, end = timing.groups()
                for value in (start, end):
                    datetime.strptime(value, "%H:%M")
                if start >= end:
                    raise ValueError("invalid lesson interval")
                kind_node = lesson.select_one(".ad")
                kind = " ".join(str(text).strip() for text in kind_node.find_all(string=True, recursive=False)).strip() if kind_node else ""
                related = []
                related_kind = "teacher" if entity["kind"] == "group" else "group"
                for link in lesson.select(".teacher a[href]"):
                    href, name = source_slug(link["href"]), clean(link)
                    key = (href, related_kind)
                    if key not in links:
                        # Source display links (e.g. surname with dots) are not canonical IDs.
                        candidates = await search(name)
                        normalize = lambda s: re.sub(r"[\s._()/-]", "", s).casefold()
                        matches = [item for item in candidates if item["kind"] == related_kind and (item["id"] == href or normalize(item["name"]) == normalize(name))]
                        if len(matches) != 1:
                            raise ValueError("ambiguous linked entity")
                        links[key] = matches[0]
                    related.append(links[key])
                record = {"week": week, "weekday": weekday, "number": int(number), "title": title, "kind": " ".join(kind.split()), "start": start, "end": end, "room": room,
                          "teachers": related if entity["kind"] == "group" else [entity], "groups": [entity] if entity["kind"] == "group" else related}
                lessons.append(record)
    # Merge a teacher's identical joint-flow entries only, preserving parallel variants.
    merged: dict[str, dict] = {}
    for record in lessons:
        # Link order and duplicates in source HTML are not semantic changes.
        for field in ("groups", "teachers"):
            record[field] = sorted({item["id"]: item for item in record[field]}.values(), key=lambda item: item["id"])
        identity = {k: v for k, v in record.items() if k != "groups"}
        key = json.dumps(identity, ensure_ascii=False, sort_keys=True)
        if key not in merged:
            merged[key] = record
        else:
            groups = {g["id"]: g for g in merged[key]["groups"] + record["groups"]}
            merged[key]["groups"] = sorted(groups.values(), key=lambda g: g["id"])
    output = []
    for record in merged.values():
        for field in ("groups", "teachers"):
            record[field] = sorted({e["id"]: e for e in record[field]}.values(), key=lambda e: e["id"])
        record["id"] = hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:32]
        output.append(record)
    return sorted(output, key=lambda r: (r["week"], r["weekday"], r["start"], r["id"]))


async def get_schedule(slug: str, force: bool = False) -> dict:
    slug = canonical_slug(slug)
    token = str(uuid4())
    async with async_session_factory() as session:
        entity = await session.get(Entity, slug)
        if not entity:
            raise HTTPException(404, "Сначала выберите расписание из поиска")
        dto = entity_dto(entity)
        snapshot = await session.get(Snapshot, slug)
        fresh = snapshot and (now() - snapshot.fetched_at).total_seconds() < config.source_ttl_seconds
        if fresh and not force:
            await session.execute(update(Entity).where(Entity.id == slug).values(requested_at=now()))
            await session.commit()
            return schedule_dto(dto, snapshot)
        claimed = (await session.execute(update(Entity).where(Entity.id == slug, (Entity.refresh_until.is_(None)) | (Entity.refresh_until < now())).values(refresh_token=token, refresh_until=now() + timedelta(minutes=10), requested_at=now()).returning(Entity.id))).scalar_one_or_none()
        await session.commit()
    if claimed:
        try:
            html = await source_get("/" + quote(slug))
            lessons = await parse_schedule(html, dto)
            digest = hashlib.sha256(json.dumps(lessons, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            async with async_session_factory() as session:
                entity = (await session.execute(select(Entity).where(Entity.id == slug).with_for_update())).scalar_one()
                if entity.refresh_token == token and entity.refresh_until > now():
                    current = await session.get(Snapshot, slug)
                    if current is None:
                        session.add(Snapshot(entity_id=slug, lessons=lessons, content_hash=digest, fetched_at=now(), changed_at=now()))
                    elif digest == current.content_hash:
                        current.fetched_at = now()
                        entity.candidate_hash = None
                    elif entity.candidate_hash == digest and entity.candidate_at and (now() - entity.candidate_at).total_seconds() >= 30:
                        session.add(SnapshotArchive(entity_id=slug, lessons=current.lessons, content_hash=current.content_hash, fetched_at=current.fetched_at))
                        current.lessons, current.content_hash = lessons, digest
                        current.fetched_at = current.changed_at = now()
                        entity.candidate_hash = None
                    else:
                        entity.candidate_hash, entity.candidate_at = digest, now()
                    entity.refresh_token = None
                    entity.refresh_until = None
                await session.commit()
        except (HTTPException, ValueError, KeyError, TypeError):
            # Preserve last-good snapshot and back off instead of replacing with empty data.
            async with async_session_factory() as session:
                await session.execute(update(Entity).where(Entity.id == slug, Entity.refresh_token == token).values(refresh_token=None, refresh_until=now() + timedelta(minutes=1)))
                await session.commit()
            if snapshot is None:
                raise HTTPException(503, "Нет достоверного снимка расписания") from None
    elif snapshot is None:
        raise HTTPException(503, "Расписание загружается, повторите запрос")
    async with async_session_factory() as session:
        snapshot = await session.get(Snapshot, slug)
        if snapshot is None:
            raise HTTPException(503, "Снимок недоступен")
        return schedule_dto(dto, snapshot)


def schedule_dto(entity: dict, snapshot: Snapshot) -> dict:
    return {"entity": entity, "fetched_at": snapshot.fetched_at.isoformat(), "stale": (now() - snapshot.fetched_at).total_seconds() >= config.source_ttl_seconds,
            "template": True, "lessons": snapshot.lessons, "current_week": week_at(now()), "timezone": config.timezone}
