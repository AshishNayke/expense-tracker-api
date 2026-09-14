"""add user ownership to expenses

Revision ID: 2a236cdca06e
Revises: f9a1cf7d7774
Create Date: 2026-09-14 18:38:05.934402

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2a236cdca06e'
down_revision: str | Sequence[str] | None = 'f9a1cf7d7774'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "expenses",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )

    op.execute(
        "UPDATE expenses SET user_id = 4 WHERE user_id IS NULL"
    )

    op.alter_column(
        "expenses",
        "user_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_foreign_key(
        "fk_expenses_user_id_users",
        "expenses",
        "users",
        ["user_id"],
        ["id"],
    )

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_expenses_user_id_users",
        "expenses",
        type_="foreignkey",
    )
    op.drop_column("expenses", "user_id")
