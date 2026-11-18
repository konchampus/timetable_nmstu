"""Persistent multiplayer rooms, membership, commands and chat. Frozen schema."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
revision = '0005_monopoly'
down_revision = '0004_fishing_progression'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('monopoly_rooms',
        sa.Column('id',pg.UUID(as_uuid=True),primary_key=True),
        sa.Column('code',sa.String(24),nullable=False,unique=True),
        sa.Column('title',sa.String(60),nullable=False),
        sa.Column('host',sa.String(36),nullable=False),
        sa.Column('public',sa.Boolean(),nullable=False),
        sa.Column('capacity',sa.Integer(),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('event_version',sa.BigInteger(),nullable=False,server_default='1'),
        sa.Column('status',sa.String(12),nullable=False),
        sa.Column('state',pg.JSONB(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('deadline',sa.DateTime(timezone=True)))
    op.create_index('ix_monopoly_rooms_status','monopoly_rooms',['status'])
    op.create_table('monopoly_members',
        sa.Column('id',pg.UUID(as_uuid=True),primary_key=True),
        sa.Column('room_id',pg.UUID(as_uuid=True),sa.ForeignKey('monopoly_rooms.id',ondelete='CASCADE'),nullable=False),
        sa.Column('user_id',sa.BigInteger(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('generation',sa.String(36),nullable=False),
        sa.UniqueConstraint('room_id','user_id',name='uq_monopoly_member'))
    op.create_index('ix_monopoly_members_user_id','monopoly_members',['user_id'])
    op.create_table('monopoly_commands',
        sa.Column('id',pg.UUID(as_uuid=True),primary_key=True),
        sa.Column('user_id',sa.BigInteger(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('key',sa.String(36),nullable=False),
        sa.Column('fingerprint',sa.String(64),nullable=False),
        sa.Column('response',pg.JSONB(),nullable=False),
        sa.UniqueConstraint('user_id','key',name='uq_monopoly_command'))
    op.create_table('monopoly_messages',
        sa.Column('id',pg.UUID(as_uuid=True),primary_key=True),
        sa.Column('room_id',pg.UUID(as_uuid=True),sa.ForeignKey('monopoly_rooms.id',ondelete='CASCADE'),nullable=False),
        sa.Column('member_id',pg.UUID(as_uuid=True),sa.ForeignKey('monopoly_members.id',ondelete='CASCADE'),nullable=False),
        sa.Column('text',sa.String(500),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_monopoly_message_room_time','monopoly_messages',['room_id','created_at'])


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM monopoly_rooms) THEN
    RAISE EXCEPTION 'Monopoly rooms exist: export data before an explicit destructive downgrade';
    END IF; END $$""")
    for table in ['monopoly_messages','monopoly_commands','monopoly_members','monopoly_rooms']:
        op.drop_table(table)
