"""Add explicit fixture import counters.

Revision ID: d3f6a9c20e11
Revises: b1813416469a
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3f6a9c20e11"
down_revision: str | None = "b1813416469a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COUNTERS = (
    "courses_seen",
    "sections_seen",
    "sections_imported",
    "sections_skipped",
    "meetings_imported",
    "malformed_records",
)


def upgrade() -> None:
    for name in COUNTERS:
        op.add_column("import_runs", sa.Column(name, sa.Integer(), nullable=True))
        op.create_check_constraint(
            f"ck_import_runs_{name}_nonnegative",
            "import_runs",
            f"{name} IS NULL OR {name} >= 0",
        )


def downgrade() -> None:
    for name in reversed(COUNTERS):
        op.drop_constraint(f"ck_import_runs_{name}_nonnegative", "import_runs", type_="check")
        op.drop_column("import_runs", name)
