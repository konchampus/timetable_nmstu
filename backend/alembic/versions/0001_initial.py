"""Frozen initial core and game schema. No runtime create_all or mutable model DDL."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def owner(primary_key=False):
    return sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=primary_key, nullable=False)


def stamp(name, nullable=False, server_default=None):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable, server_default=server_default)


def upgrade():
    op.create_table("users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("account_generation", sa.String(36), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("bot_blocked", sa.Boolean(), nullable=False),
        sa.Column("bot_started", sa.Boolean(), nullable=False),
        stamp("created_at", server_default=sa.func.now()),
    )
    op.create_table("user_settings", owner(True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("preferences", pg.JSONB(), nullable=False),
        sa.Column("leaderboard_visible", sa.Boolean(), nullable=False),
        sa.Column("nickname", sa.String(40), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_settings_version"),
        sa.CheckConstraint("NOT leaderboard_visible OR length(trim(nickname)) > 0", name="ck_settings_consent_nickname"),
    )
    op.create_table("auth_sessions", sa.Column("digest", sa.String(64), primary_key=True), owner(), stamp("expires_at"))
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_table("user_revocations", sa.Column("digest", sa.String(64), primary_key=True), stamp("revoked_at"), stamp("expires_at"))
    op.create_index("ix_user_revocations_expires_at", "user_revocations", ["expires_at"])
    op.create_table("auth_replays", sa.Column("digest", sa.String(64), primary_key=True), stamp("expires_at"))
    op.create_index("ix_auth_replays_expires_at", "auth_replays", ["expires_at"])
    op.create_table("rate_buckets", sa.Column("key", sa.String(128), primary_key=True), sa.Column("count", sa.Integer(), nullable=False), stamp("expires_at"))
    op.create_index("ix_rate_buckets_expires_at", "rate_buckets", ["expires_at"])
    op.create_table("notes", sa.Column("id", sa.String(36), primary_key=True), owner(),
        sa.Column("title", sa.String(200), nullable=False), sa.Column("text", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False), sa.Column("date", sa.String(10)),
        sa.Column("lesson_id", sa.String(64)), sa.Column("subject", sa.String(200)),
        sa.Column("done", sa.Boolean(), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        stamp("updated_at", server_default=sa.func.now()),
        sa.CheckConstraint("version >= 1", name="ck_note_version"),
        sa.CheckConstraint("kind IN ('note','homework')", name="ck_note_kind"),
        sa.CheckConstraint("length(text) <= 5000", name="ck_note_text"),
    )
    op.create_index("ix_notes_user_id", "notes", ["user_id"])
    op.create_table("schedule_entities", sa.Column("id", sa.String(200), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False), sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False), stamp("requested_at", server_default=sa.func.now()),
        sa.Column("refresh_token", sa.String(36)), stamp("refresh_until", True),
        sa.Column("candidate_hash", sa.String(64)), stamp("candidate_at", True),
    )
    op.create_index("ix_schedule_entities_requested_at", "schedule_entities", ["requested_at"])
    op.create_table("schedule_snapshots",
        sa.Column("entity_id", sa.String(200), sa.ForeignKey("schedule_entities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("lessons", pg.JSONB(), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False),
        stamp("fetched_at"), stamp("changed_at"),
    )
    op.create_table("schedule_snapshot_archive", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_id", sa.String(200), sa.ForeignKey("schedule_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lessons", pg.JSONB(), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False), stamp("fetched_at"),
    )
    op.create_index("ix_schedule_snapshot_archive_entity_id", "schedule_snapshot_archive", ["entity_id"])
    op.create_index("ix_schedule_snapshot_archive_fetched_at", "schedule_snapshot_archive", ["fetched_at"])
    op.create_table("search_cache", sa.Column("query", sa.String(100), primary_key=True), sa.Column("items", pg.JSONB(), nullable=False), stamp("expires_at"))
    op.create_table("source_budget", sa.Column("id", sa.Integer(), primary_key=True), stamp("next_at"))
    for table in ("favorites", "recent_views"):
        columns = [owner(True), sa.Column("entity_id", sa.String(200), sa.ForeignKey("schedule_entities.id", ondelete="CASCADE"), primary_key=True)]
        if table == "recent_views":
            columns.append(stamp("viewed_at", server_default=sa.func.now()))
        op.create_table(table, *columns)
    op.create_table("bot_interactions", owner(True), sa.Column("key", sa.String(16), nullable=False), sa.Column("data", pg.JSONB(), nullable=False), stamp("expires_at"))
    op.create_table("notification_cursors", owner(True), sa.Column("entity_id", sa.String(200), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False), sa.Column("settings_version", sa.Integer(), nullable=False))
    op.create_table("notification_jobs", sa.Column("id", sa.String(36), primary_key=True), owner(),
        sa.Column("dedupe", sa.String(64), nullable=False, unique=True),
        sa.Column("entity_id", sa.String(200), nullable=False), sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("settings_version", sa.Integer(), nullable=False), sa.Column("category", sa.String(20), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False), stamp("due_at"), stamp("expires_at"),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("lease_token", sa.String(36)), stamp("lease_until", True),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("last_error", sa.String(40)), stamp("created_at", server_default=sa.func.now()),
    )
    op.create_index("ix_notification_jobs_user_id", "notification_jobs", ["user_id"])
    op.create_index("ix_notification_due", "notification_jobs", ["status", "due_at"])

    # Frozen game-engine models, including composite owner integrity constraints.
    op.create_table("game_wallets", owner(True),
        sa.Column("balance", sa.BigInteger(), nullable=False), sa.Column("rod_level", sa.Integer(), nullable=False),
        sa.Column("collected_species", pg.JSONB(), nullable=False), sa.Column("record_grams", sa.Integer(), nullable=False), stamp("last_mutation_at", True),
        sa.CheckConstraint("balance >= 0", name="ck_game_wallet_balance"),
        sa.CheckConstraint("rod_level BETWEEN 1 AND 5", name="ck_game_rod_level"),
        sa.CheckConstraint("record_grams BETWEEN 0 AND 12000", name="ck_game_record_weight"),
        sa.CheckConstraint("jsonb_typeof(collected_species) = 'array' AND jsonb_array_length(collected_species) <= 5", name="ck_game_collection_shape"),
    )
    op.create_table("game_rounds", sa.Column("id", pg.UUID(as_uuid=True), primary_key=True), owner(),
        sa.Column("game", sa.String(20), nullable=False), sa.Column("status", sa.String(12), nullable=False),
        sa.Column("bet", sa.Integer(), nullable=False), sa.Column("payout", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("rules_version", sa.Integer(), nullable=False),
        stamp("created_at"), stamp("available_at", True), stamp("expires_at", True),
        sa.Column("public_state", pg.JSONB(), nullable=False), sa.Column("secret_state", pg.JSONB(), nullable=False), sa.Column("result", pg.JSONB()),
        sa.CheckConstraint("game IN ('slots','fishing','dice','darts','bowling','basketball','football','coin','roulette','blackjack','mines','wheel')", name="ck_game_round_game"),
        sa.CheckConstraint("status IN ('active','won','lost','push','caught','expired')", name="ck_game_round_status"),
        sa.CheckConstraint("(game = 'fishing' AND bet = 0) OR (game <> 'fishing' AND bet BETWEEN 10 AND 500)", name="ck_game_round_bet"),
        sa.CheckConstraint("payout >= 0 AND version >= 1 AND rules_version = 1", name="ck_game_round_numbers"),
        sa.CheckConstraint("(status = 'active' AND payout = 0) OR status <> 'active'", name="ck_game_active_unsettled"),
        sa.CheckConstraint("status <> 'caught' OR game = 'fishing'", name="ck_game_caught_type"),
        sa.UniqueConstraint("id", "user_id", name="uq_game_round_id_owner"),
    )
    op.create_index("uq_game_active_owner_type", "game_rounds", ["user_id", "game"], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_index("ix_game_round_owner_created", "game_rounds", ["user_id", "created_at"])
    op.create_table("game_wallet_ledger", sa.Column("id", pg.UUID(as_uuid=True), primary_key=True), owner(),
        sa.Column("round_id", pg.UUID(as_uuid=True)), sa.Column("event", sa.String(180), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False), sa.Column("balance_after", sa.BigInteger(), nullable=False), stamp("created_at"),
        sa.UniqueConstraint("user_id", "event", name="uq_game_ledger_event"),
        sa.ForeignKeyConstraint(["round_id", "user_id"], ["game_rounds.id", "game_rounds.user_id"], ondelete="CASCADE", name="fk_game_ledger_round_owner"),
        sa.CheckConstraint("amount <> 0 AND balance_after >= 0", name="ck_game_ledger_amount"),
    )
    op.create_index("ix_game_ledger_owner_created", "game_wallet_ledger", ["user_id", "created_at"])
    op.create_table("game_actions", sa.Column("id", pg.UUID(as_uuid=True), primary_key=True), owner(),
        sa.Column("key", sa.String(128), nullable=False), sa.Column("operation", sa.String(100), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False), sa.Column("response", pg.JSONB(), nullable=False), stamp("created_at"),
        sa.UniqueConstraint("user_id", "key", name="uq_game_action_owner_key"),
    )
    op.create_table("game_daily_claims", owner(True), sa.Column("day", sa.Date(), primary_key=True), stamp("created_at"))
    op.create_table("game_fishing_catches", sa.Column("id", pg.UUID(as_uuid=True), primary_key=True), owner(),
        sa.Column("round_id", pg.UUID(as_uuid=True), nullable=False), sa.Column("species", sa.String(50), nullable=False),
        sa.Column("rarity", sa.String(20), nullable=False), sa.Column("weight_grams", sa.Integer(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False), stamp("caught_at"), stamp("sold_at", True),
        sa.UniqueConstraint("round_id", name="uq_game_catch_round"),
        sa.ForeignKeyConstraint(["round_id", "user_id"], ["game_rounds.id", "game_rounds.user_id"], ondelete="CASCADE", name="fk_game_catch_round_owner"),
        sa.CheckConstraint("value > 0 AND weight_grams > 0", name="ck_game_catch_value"),
    )
    op.create_index("ix_game_catch_owner_unsold", "game_fishing_catches", ["user_id"], postgresql_where=sa.text("sold_at IS NULL"))


def downgrade():
    # Explicit reverse dependency order, only this application's tables.
    for table in (
        "game_fishing_catches", "game_daily_claims", "game_actions", "game_wallet_ledger", "game_rounds", "game_wallets",
        "notification_jobs", "notification_cursors", "bot_interactions", "recent_views", "favorites", "source_budget", "search_cache",
        "schedule_snapshot_archive", "schedule_snapshots", "schedule_entities", "notes", "rate_buckets", "auth_replays",
        "user_revocations", "auth_sessions", "user_settings", "users",
    ):
        op.drop_table(table)
