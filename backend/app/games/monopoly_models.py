"""Room aggregate is locked once per command; members fence account generations."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class MonopolyRoom(Base):
    __tablename__ = 'monopoly_rooms'
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(60), nullable=False)
    host: Mapped[str] = mapped_column(String(36), nullable=False)
    public: Mapped[bool] = mapped_column(Boolean, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    event_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default='lobby', index=True)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class MonopolyMember(Base):
    __tablename__ = 'monopoly_members'
    __table_args__ = (UniqueConstraint('room_id','user_id',name='uq_monopoly_member'),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('monopoly_rooms.id',ondelete='CASCADE'), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id',ondelete='CASCADE'), nullable=False, index=True)
    generation: Mapped[str] = mapped_column(String(36), nullable=False)

class MonopolyCommand(Base):
    __tablename__ = 'monopoly_commands'
    __table_args__ = (UniqueConstraint('user_id','key',name='uq_monopoly_command'),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id',ondelete='CASCADE'), nullable=False)
    key: Mapped[str] = mapped_column(String(36), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False)

class MonopolyMessage(Base):
    __tablename__ = 'monopoly_messages'
    __table_args__ = (Index('ix_monopoly_message_room_time','room_id','created_at'),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('monopoly_rooms.id',ondelete='CASCADE'), nullable=False)
    member_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('monopoly_members.id',ondelete='CASCADE'), nullable=False)
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
