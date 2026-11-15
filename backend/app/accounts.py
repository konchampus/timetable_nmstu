from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from .models import NotificationJob, Settings, User
from .schemas import SettingsDTO
from .security import lock_authenticated_user


async def lock_user(session: AsyncSession, user_id: int, *, trusted_bot: bool = False) -> User:
    if not trusted_bot:
        raise HTTPException(401, "Web service must revalidate authenticated principal")
    user = (await session.execute(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if not user or not user.active:
        raise HTTPException(401, "Аккаунт недоступен")
    return user


def settings_dto(row: Settings) -> SettingsDTO:
    return SettingsDTO(**{**row.preferences, "version": row.version, "leaderboard_visible": row.leaderboard_visible, "nickname": row.nickname})


async def read_settings(session: AsyncSession, user_id: int) -> SettingsDTO:
    row = await session.get(Settings, user_id)
    if row is None:
        raise HTTPException(401, "Аккаунт недоступен")
    return settings_dto(row)


async def save_settings(session: AsyncSession, user_id: int, dto: SettingsDTO, *, principal: User | None = None, trusted_bot: bool = False) -> SettingsDTO:
    if principal is not None:
        if principal.id != user_id:
            raise HTTPException(401, "Неверная сессия")
        await lock_authenticated_user(session, principal)
    else:
        await lock_user(session, user_id, trusted_bot=trusted_bot)
    row = (await session.execute(select(Settings).where(Settings.user_id == user_id).with_for_update().execution_options(populate_existing=True))).scalar_one()
    if dto.version != row.version:
        raise HTTPException(409, "Настройки изменены другим устройством")
    if dto.home_entity:
        from .timetable import canonical_slug
        from .models import Entity
        canonical_slug(dto.home_entity)
        entity = await session.get(Entity, dto.home_entity)
        if entity is None or entity.kind != "group":
            raise HTTPException(422, "Выберите группу из поиска")
        dto.home_name = entity.name
    else:
        dto.home_name = None
    row.preferences = dto.model_dump(mode="json", exclude={"version", "nickname", "leaderboard_visible"})
    row.nickname = dto.nickname
    row.leaderboard_visible = dto.leaderboard_visible
    row.version += 1
    # In-flight sends recheck the new version; pending jobs are invalidated immediately.
    await session.execute(delete(NotificationJob).where(NotificationJob.user_id == user_id, NotificationJob.status.in_(["pending", "claimed"])))
    await session.commit()
    return settings_dto(row)
