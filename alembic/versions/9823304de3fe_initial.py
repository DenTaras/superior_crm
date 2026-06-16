"""initial

Revision ID: 9823304de3fe
Revises: 
Create Date: 2026-06-16 15:56:06.404893

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9823304de3fe'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — создать все таблицы."""
    # --- clients ---
    op.create_table(
        'clients',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('last_name', sa.String(), nullable=True),
        sa.Column('patronymic', sa.String(), nullable=True),
        sa.Column('birth_year', sa.Integer(), nullable=True),
        sa.Column('birth_place', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('remaining_sessions', sa.Integer(), server_default=sa.text('1'), nullable=True),
    )
    # --- slots ---
    op.create_table(
        'slots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('capacity', sa.Integer(), server_default=sa.text('4'), nullable=True),
    )
    # --- bookings ---
    op.create_table(
        'bookings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id'), nullable=True),
        sa.Column('slot_id', sa.Integer(), sa.ForeignKey('slots.id'), nullable=True),
    )
    # --- journal ---
    op.create_table(
        'journal',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('slot_time', sa.DateTime(), nullable=True),
        sa.Column('clients', sa.String(), nullable=True),
        sa.Column('comments', sa.String(), nullable=True),
    )
    # --- training_notes ---
    op.create_table(
        'training_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('slot_id', sa.Integer(), sa.ForeignKey('slots.id'), nullable=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id'), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_training_notes_slot_id', 'training_notes', ['slot_id'])
    op.create_index('ix_training_notes_client_id', 'training_notes', ['client_id'])


def downgrade() -> None:
    """Downgrade schema — удалить все таблицы."""
    op.drop_table('training_notes')
    op.drop_table('journal')
    op.drop_table('bookings')
    op.drop_table('slots')
    op.drop_table('clients')
