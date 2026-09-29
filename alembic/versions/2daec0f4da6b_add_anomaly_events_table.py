from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '2daec0f4da6b'
down_revision: Union[str, None] = '562c041130ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('anomaly_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('server_id', sa.Integer(), nullable=False),
    sa.Column('scenario_type', sa.String(), nullable=False),
    sa.Column('start_ts', sa.DateTime(), nullable=False),
    sa.Column('end_ts', sa.DateTime(), nullable=True),
    sa.Column('parameters', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['server_id'], ['servers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_anomaly_events_id'), 'anomaly_events', ['id'], unique=False)
    op.create_index(op.f('ix_anomaly_events_scenario_type'), 'anomaly_events', ['scenario_type'], unique=False)
    op.create_index(op.f('ix_anomaly_events_server_id'), 'anomaly_events', ['server_id'], unique=False)
    op.create_index(op.f('ix_anomaly_events_start_ts'), 'anomaly_events', ['start_ts'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_anomaly_events_start_ts'), table_name='anomaly_events')
    op.drop_index(op.f('ix_anomaly_events_server_id'), table_name='anomaly_events')
    op.drop_index(op.f('ix_anomaly_events_scenario_type'), table_name='anomaly_events')
    op.drop_index(op.f('ix_anomaly_events_id'), table_name='anomaly_events')
    op.drop_table('anomaly_events')
