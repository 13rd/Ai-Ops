from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '8f94c5b321bf'
down_revision: Union[str, None] = '2f584dc0d9f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('console_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_token', sa.String(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('server_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=False),
    sa.Column('ended_at', sa.DateTime(), nullable=True),
    sa.Column('duration_seconds', sa.Integer(), nullable=True),
    sa.Column('client_ip', sa.String(), nullable=True),
    sa.Column('terminated_by_user_id', sa.Integer(), nullable=True),
    sa.Column('termination_reason', sa.String(), nullable=True),
    sa.Column('session_metadata', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['server_id'], ['servers.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['terminated_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_console_sessions_id'), 'console_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_console_sessions_server_id'), 'console_sessions', ['server_id'], unique=False)
    op.create_index(op.f('ix_console_sessions_session_token'), 'console_sessions', ['session_token'], unique=True)
    op.create_index(op.f('ix_console_sessions_status'), 'console_sessions', ['status'], unique=False)
    op.create_index(op.f('ix_console_sessions_user_id'), 'console_sessions', ['user_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_console_sessions_user_id'), table_name='console_sessions')
    op.drop_index(op.f('ix_console_sessions_status'), table_name='console_sessions')
    op.drop_index(op.f('ix_console_sessions_session_token'), table_name='console_sessions')
    op.drop_index(op.f('ix_console_sessions_server_id'), table_name='console_sessions')
    op.drop_index(op.f('ix_console_sessions_id'), table_name='console_sessions')
    op.drop_table('console_sessions')
