from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '562c041130ce'
down_revision: Union[str, None] = '8f94c5b321bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
