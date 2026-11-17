"""Owned game tables; import this module into Alembic's Base.metadata."""
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Wallet(Base):
    __tablename__ = "game_wallets"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_game_wallet_balance"),
        CheckConstraint("rod_level BETWEEN 1 AND 5", name="ck_game_rod_level"),
        CheckConstraint("record_grams BETWEEN 0 AND 12000", name="ck_game_record_weight"),
        CheckConstraint("jsonb_typeof(collected_species) = 'array' AND jsonb_array_length(collected_species) <= 7", name="ck_game_collection_shape"),
        CheckConstraint("fishing_location IN ('shore','river','mountain','golden','carp')", name="ck_game_fishing_location"),
        CheckConstraint("fishing_skin IN ('angler','bear')", name="ck_game_fishing_skin"),
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    rod_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fishing_location: Mapped[str] = mapped_column(String(20), nullable=False, default="shore", server_default="shore")
    fishing_skin: Mapped[str] = mapped_column(String(20), nullable=False, default="angler", server_default="angler")
    collected_species: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    record_grams: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_mutation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GameRound(Base):
    __tablename__ = "game_rounds"
    __table_args__ = (
        CheckConstraint("game IN ('slots','fishing','dice','darts','bowling','basketball','football','coin','roulette','blackjack','mines','wheel')", name="ck_game_round_game"),
        CheckConstraint("status IN ('active','won','lost','push','caught','expired')", name="ck_game_round_status"),
        CheckConstraint("(game = 'fishing' AND bet = 0) OR (game <> 'fishing' AND bet BETWEEN 10 AND 500)", name="ck_game_round_bet"),
        CheckConstraint("payout >= 0 AND version >= 1 AND rules_version = 1", name="ck_game_round_numbers"),
        CheckConstraint("(status = 'active' AND payout = 0) OR status <> 'active'", name="ck_game_active_unsettled"),
        CheckConstraint("status <> 'caught' OR game = 'fishing'", name="ck_game_caught_type"),
        UniqueConstraint("id", "user_id", name="uq_game_round_id_owner"),
        Index("uq_game_active_owner_type", "user_id", "game", unique=True, postgresql_where=text("status = 'active'")),
        Index("ix_game_round_owner_created", "user_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    game: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="active")
    bet: Mapped[int] = mapped_column(Integer, nullable=False)
    payout: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rules_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    public_state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    secret_state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB)


class WalletLedger(Base):
    __tablename__ = "game_wallet_ledger"
    __table_args__ = (
        UniqueConstraint("user_id", "event", name="uq_game_ledger_event"),
        ForeignKeyConstraint(["round_id", "user_id"], ["game_rounds.id", "game_rounds.user_id"], ondelete="CASCADE", name="fk_game_ledger_round_owner"),
        CheckConstraint("amount <> 0 AND balance_after >= 0", name="ck_game_ledger_amount"),
        Index("ix_game_ledger_owner_created", "user_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    round_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    event: Mapped[str] = mapped_column(String(180), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GameAction(Base):
    """Per-user idempotency journal covering every game/economy mutation."""
    __tablename__ = "game_actions"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_game_action_owner_key"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DailyClaim(Base):
    __tablename__ = "game_daily_claims"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GameDailyQuota(Base):
    """Local-day counters; every access is serialized by the owning User lock."""
    __tablename__ = "game_daily_quotas"
    __table_args__ = (
        CheckConstraint("regular_attempts >= 0 AND regular_catches >= 0 AND boss_attempts >= 0 AND sport_rounds >= 0", name="ck_game_quota_counts"),
        CheckConstraint("jsonb_typeof(claimed_bosses) = 'array' AND jsonb_array_length(claimed_bosses) <= 4", name="ck_game_quota_bosses"),
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    regular_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    regular_catches: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    boss_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sport_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    claimed_bosses: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))


class FishingCatch(Base):
    __tablename__ = "game_fishing_catches"
    __table_args__ = (
        UniqueConstraint("round_id", name="uq_game_catch_round"),
        ForeignKeyConstraint(["round_id", "user_id"], ["game_rounds.id", "game_rounds.user_id"], ondelete="CASCADE", name="fk_game_catch_round_owner"),
        CheckConstraint("value > 0 AND weight_grams > 0", name="ck_game_catch_value"),
        Index("ix_game_catch_owner_unsold", "user_id", postgresql_where=text("sold_at IS NULL")),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    round_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    species: Mapped[str] = mapped_column(String(50), nullable=False)
    rarity: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_grams: Mapped[int] = mapped_column(Integer, nullable=False)
    caught_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
