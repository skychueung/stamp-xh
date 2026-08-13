"""pipeline ownership and idempotency indexes

Revision ID: 9b2e4f7a1c30
Revises: 1e3bcd1d779f
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9b2e4f7a1c30"
down_revision: Union[str, Sequence[str], None] = "1e3bcd1d779f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(table_name: str) -> set[str]:
    return {entry["name"] for entry in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "projects" in tables:
        columns = {column["name"] for column in inspector.get_columns("projects")}
        if "owner_id" not in columns:
            with op.batch_alter_table("projects") as batch_op:
                batch_op.add_column(sa.Column("owner_id", sa.String(36), nullable=True))
        if "ix_projects_owner_id" not in _index_names("projects"):
            op.create_index("ix_projects_owner_id", "projects", ["owner_id"], unique=False)
    if "pipeline_runs" in tables and "ix_pipeline_runs_created_by" not in _index_names("pipeline_runs"):
        op.create_index("ix_pipeline_runs_created_by", "pipeline_runs", ["created_by"], unique=False)
    if "pipeline_steps" in tables and "uq_pipeline_run_step" not in _index_names("pipeline_steps"):
        op.create_index(
            "uq_pipeline_run_step",
            "pipeline_steps",
            ["pipeline_run_id", "step_name"],
            unique=True,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "projects" in tables:
        if "ix_projects_owner_id" in _index_names("projects"):
            op.drop_index("ix_projects_owner_id", table_name="projects")
        columns = {column["name"] for column in inspector.get_columns("projects")}
        if "owner_id" in columns:
            with op.batch_alter_table("projects") as batch_op:
                batch_op.drop_column("owner_id")
    if "pipeline_steps" in tables and "uq_pipeline_run_step" in _index_names("pipeline_steps"):
        op.drop_index("uq_pipeline_run_step", table_name="pipeline_steps")
    if "pipeline_runs" in tables and "ix_pipeline_runs_created_by" in _index_names("pipeline_runs"):
        op.drop_index("ix_pipeline_runs_created_by", table_name="pipeline_runs")
