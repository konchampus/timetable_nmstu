from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from .accounts import read_settings, save_settings
from .config import config
from .db import get_session
from .models import AuthSession, Entity, Favorite, Note, Recent, Snapshot, User, UserRevocation
from .schemas import AuthInput, AuthResponse, DeleteAccount, EntityList, FavoriteInput, MeDTO, NoteCreate, NoteDTO, NoteInput, NoteList, NoteUpdate, ScheduleDTO, SettingsDTO
from .security import current_user, exchange_init_data, now, rate_limit, revocation_digest, lock_authenticated_user
from .timetable import canonical_slug, entity_dto, get_schedule, search

router = APIRouter()


@router.post("/auth/telegram", response_model=AuthResponse)
async def authenticate(body: AuthInput, request: Request):
    return await exchange_init_data(body.init_data, request)


@router.get("/me", response_model=MeDTO)
async def me(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    locked = await lock_authenticated_user(session, user)
    return {"id": locked.id, "name": locked.name, "account_generation": locked.account_generation, "settings": await read_settings(session, locked.id)}


@router.put("/settings", response_model=SettingsDTO)
async def settings(body: SettingsDTO, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    return await save_settings(session, user.id, body, principal=user)


@router.delete("/me", status_code=204)
async def remove_account(body: DeleteAccount, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    row = await lock_authenticated_user(session, user)
    row.active = False
    await session.flush()
    await session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    # All owner FKs (including game ledger and rounds) cascade. Game model imports
    # belong in app startup/Alembic, never in this module or models.py.
    revoked_at = now()
    await session.execute(insert(UserRevocation).values(digest=revocation_digest(user.id), revoked_at=revoked_at, expires_at=revoked_at + timedelta(seconds=config.auth_max_age + 60)).on_conflict_do_update(index_elements=[UserRevocation.digest], set_={"revoked_at": revoked_at, "expires_at": revoked_at + timedelta(seconds=config.auth_max_age + 60)}))
    await session.delete(row)
    await session.commit()
    return Response(status_code=204)


@router.get("/search", response_model=EntityList)
async def find(q: str = Query(min_length=2, max_length=100), user: User = Depends(current_user)):
    await rate_limit(str(user.id), "search", 20)
    return {"items": await search(q)}


@router.get("/schedule", response_model=ScheduleDTO)
async def schedule(entity: str = Query(max_length=200), user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    result = await get_schedule(entity)
    await lock_authenticated_user(session, user)
    await session.execute(insert(Recent).values(user_id=user.id, entity_id=entity, viewed_at=now()).on_conflict_do_update(index_elements=[Recent.user_id, Recent.entity_id], set_={"viewed_at": now()}))
    old = select(Recent.entity_id).where(Recent.user_id == user.id).order_by(Recent.viewed_at.desc(), Recent.entity_id).offset(10)
    await session.execute(delete(Recent).where(Recent.user_id == user.id, Recent.entity_id.in_(old)))
    await session.commit()
    return result


@router.get("/favorites", response_model=EntityList)
async def favorites(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await lock_authenticated_user(session, user)
    rows = (await session.execute(select(Entity).join(Favorite, Favorite.entity_id == Entity.id).where(Favorite.user_id == user.id).order_by(Entity.name))).scalars()
    return {"items": [entity_dto(row) for row in rows]}


@router.put("/favorites/{entity}", status_code=204)
async def favorite(entity: str, body: FavoriteInput, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    canonical_slug(entity)
    await lock_authenticated_user(session, user)
    source = await session.get(Entity, entity)
    if source is None:
        raise HTTPException(404, "Расписание не найдено")
    # Never let untrusted favorite labels rewrite the shared source catalogue.
    if body.kind != source.kind:
        raise HTTPException(422, "Тип расписания не совпадает")
    count = len((await session.execute(select(Favorite.entity_id).where(Favorite.user_id == user.id).limit(101))).all())
    if count >= 100 and await session.get(Favorite, (user.id, entity)) is None:
        raise HTTPException(422, "Не более 100 избранных расписаний")
    await session.execute(insert(Favorite).values(user_id=user.id, entity_id=entity).on_conflict_do_nothing())
    await session.commit()
    return Response(status_code=204)


@router.delete("/favorites/{entity}", status_code=204)
async def unfavorite(entity: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    canonical_slug(entity)
    await lock_authenticated_user(session, user)
    await session.execute(delete(Favorite).where(Favorite.user_id == user.id, Favorite.entity_id == entity))
    await session.commit()
    return Response(status_code=204)


@router.get("/recent", response_model=EntityList)
async def recents(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await lock_authenticated_user(session, user)
    rows = (await session.execute(select(Entity).join(Recent, Recent.entity_id == Entity.id).where(Recent.user_id == user.id).order_by(Recent.viewed_at.desc()).limit(10))).scalars()
    return {"items": [entity_dto(row) for row in rows]}


@router.delete("/recent/{entity}", status_code=204)
async def forget_recent(entity: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    canonical_slug(entity)
    await lock_authenticated_user(session, user)
    await session.execute(delete(Recent).where(Recent.user_id == user.id, Recent.entity_id == entity))
    await session.commit()
    return Response(status_code=204)


def note_dto(row: Note, snapshots: dict[str, Snapshot]) -> dict:
    result = {key: getattr(row, key) for key in ("id", "version", "title", "text", "kind", "date", "lesson_id", "source_entity", "subject", "done", "updated_at")}
    snapshot = snapshots.get(row.source_entity)
    if not row.lesson_id:
        status = "unlinked"
    elif not snapshot or (now() - snapshot.fetched_at).total_seconds() > config.source_max_age_seconds:
        status = "unknown"
    else:
        status = "current" if any(lesson["id"] == row.lesson_id for lesson in snapshot.lessons) else "changed"
    return {**result, "lesson_status": status}


async def note_snapshots(session: AsyncSession, rows: list[Note]) -> dict[str, Snapshot]:
    # Only the referenced public cached templates are read; no network under owner locks.
    entities = {row.source_entity for row in rows if row.source_entity and row.lesson_id}
    if not entities:
        return {}
    snapshots = (await session.scalars(select(Snapshot).where(Snapshot.entity_id.in_(entities)))).all()
    return {snapshot.entity_id: snapshot for snapshot in snapshots}


async def validate_note_source(session: AsyncSession, source: str | None):
    if source:
        canonical_slug(source)
        if await session.get(Entity, source) is None:
            raise HTTPException(422, "Выберите расписание из поиска")


@router.get("/notes", response_model=NoteList)
async def notes(q: str = Query(default="", max_length=100), kind: str | None = Query(default=None, pattern="^(note|homework)$"), offset: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=100), user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await lock_authenticated_user(session, user)
    statement = select(Note).where(Note.user_id == user.id)
    if q:
        statement = statement.where(Note.title.icontains(q, autoescape=True) | Note.text.icontains(q, autoescape=True) | Note.subject.icontains(q, autoescape=True))
    if kind:
        statement = statement.where(Note.kind == kind)
    rows = list((await session.scalars(statement.order_by(Note.updated_at.desc(), Note.id).offset(offset).limit(limit))).all())
    snapshots = await note_snapshots(session, rows)
    return {"items": [note_dto(row, snapshots) for row in rows]}


@router.post("/notes", status_code=201, response_model=NoteDTO)
async def create_note(body: NoteCreate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await lock_authenticated_user(session, user)
    await validate_note_source(session, body.source_entity)
    values = body.model_dump(mode="json", exclude={"request_id"})
    note_id = str(body.request_id)
    # The owner lock serializes same-user retries; PK conflict handling also covers
    # simultaneous UUID reuse by another owner without exposing their payload.
    await session.execute(insert(Note).values(id=note_id, user_id=user.id, **values, updated_at=now()).on_conflict_do_nothing(index_elements=[Note.id]))
    row = await session.get(Note, note_id)
    if row is None:
        raise HTTPException(409, "Конкурентное изменение; повторите запрос")
    if row.user_id != user.id:
        raise HTTPException(404, "Заметка не найдена")
    if any(getattr(row, field) != value for field, value in values.items()):
        raise HTTPException(409, "request_id уже использован с другими данными")
    result = note_dto(row, await note_snapshots(session, [row]))
    await session.commit()
    return result


@router.put("/notes/{note_id}", response_model=NoteDTO)
async def update_note(note_id: str, body: NoteUpdate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await lock_authenticated_user(session, user)
    row = (await session.execute(select(Note).where(Note.id == note_id, Note.user_id == user.id).with_for_update())).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Заметка не найдена")
    if row.version != body.version:
        raise HTTPException(409, "Заметка изменена другим устройством")
    await validate_note_source(session, body.source_entity)
    for key, value in body.model_dump(mode="json", exclude={"version"}).items():
        setattr(row, key, value)
    row.version += 1
    row.updated_at = now()
    result = note_dto(row, await note_snapshots(session, [row]))
    await session.commit()
    return result


@router.delete("/notes/{note_id}", status_code=204)
async def remove_note(note_id: str, version: int = Query(ge=1), user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await lock_authenticated_user(session, user)
    row = (await session.execute(select(Note).where(Note.id == note_id, Note.user_id == user.id).with_for_update())).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Заметка не найдена")
    if row.version != version:
        raise HTTPException(409, "Заметка изменена другим устройством")
    await session.delete(row)
    await session.commit()
    return Response(status_code=204)
