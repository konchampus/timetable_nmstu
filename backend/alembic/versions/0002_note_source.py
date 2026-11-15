"""Preserve the public timetable origin of a note without deleting old notes."""
from alembic import op
import sqlalchemy as sa

revision = "0002_note_source"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("notes", sa.Column("source_entity", sa.String(200), nullable=True))


def downgrade():
    # Only the reference is removed; private note content remains intact.
    op.drop_column("notes", "source_entity")
