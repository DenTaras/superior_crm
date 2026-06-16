"""add_unique_constraint_booking

Revision ID: 99538d0a78a0
Revises: 9823304de3fe
Create Date: 2026-06-16 17:33:57.849372

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99538d0a78a0'
down_revision: Union[str, Sequence[str], None] = '9823304de3fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — добавить unique constraint (slot_id, client_id)."""
    with op.batch_alter_table('bookings') as batch_op:
        batch_op.create_unique_constraint('uq_booking_slot_client', ['slot_id', 'client_id'])


def downgrade() -> None:
    """Downgrade schema — удалить unique constraint."""
    with op.batch_alter_table('bookings') as batch_op:
        batch_op.drop_constraint('uq_booking_slot_client', type_='unique')
