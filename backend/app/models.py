from datetime import datetime
from uuid import uuid4
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def uid() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(150), default="")
    account_generation: Mapped[str] = mapped_column(String(36), default=uid, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bot_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bot_started: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Settings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (CheckConstraint("version >= 1", name="ck_settings_version"), CheckConstraint("NOT leaderboard_visible OR length(trim(nickname)) > 0", name="ck_settings_consent_nickname"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    leaderboard_visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    nickname: Mapped[str] = mapped_column(String(40), default="", nullable=False)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class UserRevocation(Base):
    __tablename__ = "user_revocations"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AuthReplay(Base):
    __tablename__ = "auth_replays"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (CheckConstraint("version >= 1", name="ck_note_version"), CheckConstraint("kind IN ('note','homework')", name="ck_note_kind"), CheckConstraint("length(text) <= 5000", name="ck_note_text"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(10))
    date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    lesson_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_entity: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Entity(Base):
    __tablename__ = "schedule_entities"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(10))
    url: Mapped[str] = mapped_column(String(1000))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    refresh_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    refresh_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    candidate_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    candidate_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Snapshot(Base):
    __tablename__ = "schedule_snapshots"
    entity_id: Mapped[str] = mapped_column(ForeignKey("schedule_entities.id", ondelete="CASCADE"), primary_key=True)
    lessons: Mapped[list] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SnapshotArchive(Base):
    __tablename__ = "schedule_snapshot_archive"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    entity_id: Mapped[str] = mapped_column(ForeignKey("schedule_entities.id", ondelete="CASCADE"), index=True)
    lessons: Mapped[list] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SearchCache(Base):
    __tablename__ = "search_cache"
    query: Mapped[str] = mapped_column(String(100), primary_key=True)
    items: Mapped[list] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourceBudget(Base):
    __tablename__ = "source_budget"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("schedule_entities.id", ondelete="CASCADE"), primary_key=True)


class Recent(Base):
    __tablename__ = "recent_views"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("schedule_entities.id", ondelete="CASCADE"), primary_key=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BotInteraction(Base):
    __tablename__ = "bot_interactions"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(16))
    data: Mapped[dict] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NotificationCursor(Base):
    __tablename__ = "notification_cursors"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(200))
    content_hash: Mapped[str] = mapped_column(String(64))
    settings_version: Mapped[int] = mapped_column(Integer)


class NotificationJob(Base):
    __tablename__ = "notification_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    dedupe: Mapped[str] = mapped_column(String(64), unique=True)
    entity_id: Mapped[str] = mapped_column(String(200))
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    settings_version: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSONB)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_notification_due", "status", "due_at"),)
