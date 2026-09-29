from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a9fa3330d961'
down_revision: Union[str, None] = '96f2699d8d14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('alert_rules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('rule_type', sa.String(), nullable=False),
    sa.Column('is_enabled', sa.Boolean(), nullable=False),
    sa.Column('severity', sa.String(), nullable=False),
    sa.Column('config', sa.JSON(), nullable=False),
    sa.Column('server_ids', sa.JSON(), nullable=False),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alert_rules_id'), 'alert_rules', ['id'], unique=False)
    op.create_index(op.f('ix_alert_rules_rule_type'), 'alert_rules', ['rule_type'], unique=False)
    op.create_table('alerts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('severity', sa.String(), nullable=False),
    sa.Column('rule_type', sa.String(), nullable=False),
    sa.Column('server_id', sa.Integer(), nullable=True),
    sa.Column('container_id', sa.String(), nullable=True),
    sa.Column('metric_type', sa.String(), nullable=True),
    sa.Column('threshold_value', sa.String(), nullable=True),
    sa.Column('current_value', sa.String(), nullable=True),
    sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
    sa.Column('acknowledged_by_user_id', sa.Integer(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('first_triggered_at', sa.DateTime(), nullable=False),
    sa.Column('last_triggered_at', sa.DateTime(), nullable=False),
    sa.Column('additional_metadata', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['acknowledged_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['server_id'], ['servers.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_container_id'), 'alerts', ['container_id'], unique=False)
    op.create_index(op.f('ix_alerts_id'), 'alerts', ['id'], unique=False)
    op.create_index(op.f('ix_alerts_rule_type'), 'alerts', ['rule_type'], unique=False)
    op.create_index(op.f('ix_alerts_server_id'), 'alerts', ['server_id'], unique=False)
    op.create_index(op.f('ix_alerts_severity'), 'alerts', ['severity'], unique=False)
    op.create_index(op.f('ix_alerts_status'), 'alerts', ['status'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_alerts_status'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_severity'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_server_id'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_rule_type'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_id'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_container_id'), table_name='alerts')
    op.drop_table('alerts')
    op.drop_index(op.f('ix_alert_rules_rule_type'), table_name='alert_rules')
    op.drop_index(op.f('ix_alert_rules_id'), table_name='alert_rules')
    op.drop_table('alert_rules')
