"""fix expense schema

Revision ID: e23a28ae0d13
Revises: 
Create Date: 2026-09-07 19:56:41.846462

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e23a28ae0d13'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "expenses",
        "cattegory",
        new_column_name="category", 
    )
    op.create_check_constraint(
        "check_expense_amount_positive",
    	"expenses",
    	"amount > 0",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "check_expense_amount_positive",
        "expenses",
        type_="check",
    )
    op.alter_column(
        "expenses",
        "category",
        new_column_name="cattegory",
    )
