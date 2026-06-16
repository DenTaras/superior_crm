"""add_client_login

Revision ID: 5376ec12a9b0
Revises: 99538d0a78a0
Create Date: 2026-06-16 21:25:55.610464

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5376ec12a9b0'
down_revision: Union[str, Sequence[str], None] = '99538d0a78a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('clients') as batch_op:
        batch_op.add_column(sa.Column('login', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('password_hash', sa.String(), nullable=True))
        batch_op.create_unique_constraint('uq_clients_login', ['login'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('clients') as batch_op:
        batch_op.drop_constraint('uq_clients_login', type_='unique')
        batch_op.drop_column('password_hash')
        batch_op.drop_column('login')
