"""Add fishing destinations and cosmetic preference; preserve every wallet and catch."""
from alembic import op
import sqlalchemy as sa

revision = "0003_fishing_world"
down_revision = "0002_note_source"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("game_wallets", sa.Column("fishing_location", sa.String(20), nullable=False, server_default="shore"))
    op.add_column("game_wallets", sa.Column("fishing_skin", sa.String(20), nullable=False, server_default="angler"))
    op.create_check_constraint("ck_game_fishing_location", "game_wallets", "fishing_location IN ('shore','river','mountain','golden')")
    op.create_check_constraint("ck_game_fishing_skin", "game_wallets", "fishing_skin IN ('angler','bear')")
    op.drop_constraint("ck_game_collection_shape", "game_wallets", type_="check")
    op.create_check_constraint("ck_game_collection_shape", "game_wallets", "jsonb_typeof(collected_species) = 'array' AND jsonb_array_length(collected_species) <= 7")


def downgrade():
    # Never truncate someone's collection to fit an older constraint.
    # This rollback is safe only before a sixth/seventh species was collected.
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM game_wallets WHERE jsonb_array_length(collected_species) > 5) THEN
        RAISE EXCEPTION 'Cannot downgrade fishing world: collections exceed old five-species limit. Keep migration 0003.';
      END IF;
    END $$""")
    op.drop_constraint("ck_game_collection_shape", "game_wallets", type_="check")
    op.create_check_constraint("ck_game_collection_shape", "game_wallets", "jsonb_typeof(collected_species) = 'array' AND jsonb_array_length(collected_species) <= 5")
    op.drop_constraint("ck_game_fishing_skin", "game_wallets", type_="check")
    op.drop_constraint("ck_game_fishing_location", "game_wallets", type_="check")
    op.drop_column("game_wallets", "fishing_skin")
    op.drop_column("game_wallets", "fishing_location")
