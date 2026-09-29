from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '96f2699d8d14'
down_revision: Union[str, None] = '74b0d47fed99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('historical_metrics',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('server_id', sa.Integer(), nullable=False),
    sa.Column('metric_type', sa.String(), nullable=False),
    sa.Column('aggregation_level', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('period_start', sa.DateTime(), nullable=False),
    sa.Column('value_min', sa.Float(), nullable=True),
    sa.Column('value_max', sa.Float(), nullable=True),
    sa.Column('value_avg', sa.Float(), nullable=True),
    sa.Column('value_last', sa.Float(), nullable=True),
    sa.Column('sample_count', sa.Integer(), nullable=False),
    sa.Column('collected_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['server_id'], ['servers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_historical_metrics_aggregation_level'), 'historical_metrics', ['aggregation_level'], unique=False)
    op.create_index(op.f('ix_historical_metrics_collected_at'), 'historical_metrics', ['collected_at'], unique=False)
    op.create_index(op.f('ix_historical_metrics_id'), 'historical_metrics', ['id'], unique=False)
    op.create_index(op.f('ix_historical_metrics_metric_type'), 'historical_metrics', ['metric_type'], unique=False)
    op.create_index(op.f('ix_historical_metrics_period_start'), 'historical_metrics', ['period_start'], unique=False)
    op.create_index(op.f('ix_historical_metrics_server_id'), 'historical_metrics', ['server_id'], unique=False)
    op.create_index(op.f('ix_historical_metrics_timestamp'), 'historical_metrics', ['timestamp'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_historical_metrics_timestamp'), table_name='historical_metrics')
    op.drop_index(op.f('ix_historical_metrics_server_id'), table_name='historical_metrics')
    op.drop_index(op.f('ix_historical_metrics_period_start'), table_name='historical_metrics')
    op.drop_index(op.f('ix_historical_metrics_metric_type'), table_name='historical_metrics')
    op.drop_index(op.f('ix_historical_metrics_id'), table_name='historical_metrics')
    op.drop_index(op.f('ix_historical_metrics_collected_at'), table_name='historical_metrics')
    op.drop_index(op.f('ix_historical_metrics_aggregation_level'), table_name='historical_metrics')
    op.drop_table('historical_metrics')
