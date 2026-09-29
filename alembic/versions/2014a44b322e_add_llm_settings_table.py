from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '2014a44b322e'
down_revision: Union[str, None] = '436482c3bd63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('llm_settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('model', sa.String(), nullable=True),
    sa.Column('timeout_sec', sa.Integer(), nullable=True),
    sa.Column('keep_alive', sa.String(), nullable=True),
    sa.Column('prompt_template', sa.Text(), nullable=True),
    sa.Column('extra', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('llm_settings')
