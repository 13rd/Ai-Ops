from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '2f584dc0d9f2'
down_revision: Union[str, None] = 'e1a7c4cc82bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('metric_snapshots', sa.Column('active_connections', sa.Integer(), nullable=True))

def downgrade() -> None:
    op.drop_column('metric_snapshots', 'active_connections')
