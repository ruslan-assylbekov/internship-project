"""Borrowing status and due date

Adds the two columns that let a borrowing row express more than "has a
return_date": a hold (Reserved), a closed loan (Returned) and a lost book
(Lost) are otherwise indistinguishable.

Revision ID: b7c41d9e2f38
Revises: 1ea7d22b216c
Create Date: 2026-08-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c41d9e2f38'
down_revision: Union[str, Sequence[str], None] = '1ea7d22b216c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default keeps rows written before this revision valid under
    # nullable=False.
    op.add_column(
        'borrowings',
        sa.Column('status', sa.String(), nullable=False, server_default='Active'),
    )
    op.add_column('borrowings', sa.Column('due_date', sa.DateTime(), nullable=True))

    # Backfill: a pre-existing return_date means the loan was closed, and open
    # rows get the loan period the application now applies. Postgres interval
    # syntax -- this project only ever runs migrations against Postgres.
    op.execute("UPDATE borrowings SET status = 'Returned' WHERE return_date IS NOT NULL")
    op.execute(
        "UPDATE borrowings SET due_date = borrow_date + INTERVAL '14 days' "
        "WHERE return_date IS NULL AND borrow_date IS NOT NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('borrowings', 'due_date')
    op.drop_column('borrowings', 'status')
