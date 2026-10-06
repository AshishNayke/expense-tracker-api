"""add expense dates

Revision ID: 276d13a68a0e
Revises: 2a236cdca06e
Create Date: 2026-09-20 17:58:40.148324

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '276d13a68a0e'
down_revision: str | Sequence[str] | None = '2a236cdca06e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "expenses",
        sa.Column("expense_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "expenses",
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE expenses
            SET expense_date = DATE '2026-09-20'
            WHERE expense_date IS NULL
            """
        )
    )
    op.alter_column(
        "expenses",
        "expense_date",
        nullable=False,
    )

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("expenses", "created_at")
    op.drop_column("expenses", "expense_date")
