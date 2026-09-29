from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '74b0d47fed99'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('servers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('host', sa.String(), nullable=False),
    sa.Column('port', sa.Integer(), nullable=False),
    sa.Column('connection_type', sa.String(), nullable=False),
    sa.Column('environment', sa.String(), nullable=True),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('last_seen', sa.DateTime(), nullable=True),
    sa.Column('ssh_username', sa.String(), nullable=True),
    sa.Column('ssh_password', sa.Text(), nullable=True),
    sa.Column('ssh_private_key', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_servers_id'), 'servers', ['id'], unique=False)
    op.create_index(op.f('ix_servers_name'), 'servers', ['name'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('username', sa.String(), nullable=False),
    sa.Column('hashed_password', sa.String(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_table('container_snapshots',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('server_id', sa.Integer(), nullable=False),
    sa.Column('container_id', sa.String(), nullable=False),
    sa.Column('container_name', sa.String(), nullable=False),
    sa.Column('image', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('extra_data', sa.JSON(), nullable=False),
    sa.Column('collected_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['server_id'], ['servers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_container_snapshots_collected_at'), 'container_snapshots', ['collected_at'], unique=False)
    op.create_index(op.f('ix_container_snapshots_id'), 'container_snapshots', ['id'], unique=False)
    op.create_index(op.f('ix_container_snapshots_server_id'), 'container_snapshots', ['server_id'], unique=False)
    op.create_table('metric_snapshots',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('server_id', sa.Integer(), nullable=False),
    sa.Column('cpu_usage_percent', sa.Float(), nullable=True),
    sa.Column('load_average_1m', sa.Float(), nullable=True),
    sa.Column('load_average_5m', sa.Float(), nullable=True),
    sa.Column('load_average_15m', sa.Float(), nullable=True),
    sa.Column('memory_total_mb', sa.Float(), nullable=True),
    sa.Column('memory_used_mb', sa.Float(), nullable=True),
    sa.Column('memory_free_mb', sa.Float(), nullable=True),
    sa.Column('memory_usage_percent', sa.Float(), nullable=True),
    sa.Column('disk_total_gb', sa.Float(), nullable=True),
    sa.Column('disk_used_gb', sa.Float(), nullable=True),
    sa.Column('disk_free_gb', sa.Float(), nullable=True),
    sa.Column('disk_usage_percent', sa.Float(), nullable=True),
    sa.Column('network_in_bytes', sa.Float(), nullable=True),
    sa.Column('network_out_bytes', sa.Float(), nullable=True),
    sa.Column('uptime_seconds', sa.Integer(), nullable=True),
    sa.Column('extra_data', sa.JSON(), nullable=False),
    sa.Column('collected_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['server_id'], ['servers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_metric_snapshots_collected_at'), 'metric_snapshots', ['collected_at'], unique=False)
    op.create_index(op.f('ix_metric_snapshots_id'), 'metric_snapshots', ['id'], unique=False)
    op.create_index(op.f('ix_metric_snapshots_server_id'), 'metric_snapshots', ['server_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_metric_snapshots_server_id'), table_name='metric_snapshots')
    op.drop_index(op.f('ix_metric_snapshots_id'), table_name='metric_snapshots')
    op.drop_index(op.f('ix_metric_snapshots_collected_at'), table_name='metric_snapshots')
    op.drop_table('metric_snapshots')
    op.drop_index(op.f('ix_container_snapshots_server_id'), table_name='container_snapshots')
    op.drop_index(op.f('ix_container_snapshots_id'), table_name='container_snapshots')
    op.drop_index(op.f('ix_container_snapshots_collected_at'), table_name='container_snapshots')
    op.drop_table('container_snapshots')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_servers_name'), table_name='servers')
    op.drop_index(op.f('ix_servers_id'), table_name='servers')
    op.drop_table('servers')
