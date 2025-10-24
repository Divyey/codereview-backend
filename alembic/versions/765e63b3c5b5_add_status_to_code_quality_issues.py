"""Add status to code_quality_issues

Revision ID: 765e63b3c5b5
Revises: 21d5065019f1
Create Date: 2025-06-26 11:15:32.256053

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '765e63b3c5b5'
down_revision: Union[str, None] = '21d5065019f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('code_quality_issues', sa.Column('status', sa.String(), nullable=True, server_default='open'))

def downgrade() -> None:
    op.drop_column('code_quality_issues', 'status')
