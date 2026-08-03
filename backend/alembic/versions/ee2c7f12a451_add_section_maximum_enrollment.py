"""Add optional WebTMS section enrollment capacity.

Revision ID: ee2c7f12a451
Revises: d3f6a9c20e11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ee2c7f12a451"
down_revision: str | None = "d3f6a9c20e11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sections", sa.Column("maximum_enrollment", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "maximum_enrollment_nonnegative",
        "sections",
        "maximum_enrollment IS NULL OR maximum_enrollment >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("maximum_enrollment_nonnegative", "sections", type_="check")
    op.drop_column("sections", "maximum_enrollment")
