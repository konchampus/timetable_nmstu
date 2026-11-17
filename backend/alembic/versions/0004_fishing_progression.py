"""Add local-day game quotas and carp location without resetting player data."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_fishing_progression"
down_revision = "0003_fishing_world"
branch_labels = None
depends_on = None


def upgrade():
    # Only the destination CHECK is widened; collection/species and wallet data stay intact.
    op.drop_constraint("ck_game_fishing_location", "game_wallets", type_="check")
    op.create_check_constraint("ck_game_fishing_location", "game_wallets", "fishing_location IN ('shore','river','mountain','golden','carp')")
    op.create_table(
        "game_daily_quotas",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("regular_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("regular_catches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("boss_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sport_rounds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claimed_bosses", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.CheckConstraint("regular_attempts >= 0 AND regular_catches >= 0 AND boss_attempts >= 0 AND sport_rounds >= 0", name="ck_game_quota_counts"),
        sa.CheckConstraint("jsonb_typeof(claimed_bosses) = 'array' AND jsonb_array_length(claimed_bosses) <= 4", name="ck_game_quota_bosses"),
    )


def downgrade():
    # Never rewrite a saved location or silently forget anti-farm history.
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM game_wallets WHERE fishing_location = 'carp')
         OR EXISTS (SELECT 1 FROM game_daily_quotas) THEN
        RAISE EXCEPTION 'Cannot downgrade fishing progression with carp preferences or quota history. Keep migration 0004.';
      END IF;
    END $$""")
    op.drop_table("game_daily_quotas")
    op.drop_constraint("ck_game_fishing_location", "game_wallets", type_="check")
    op.create_check_constraint("ck_game_fishing_location", "game_wallets", "fishing_location IN ('shore','river','mountain','golden')")
