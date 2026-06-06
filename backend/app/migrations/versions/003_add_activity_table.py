"""add activity table

Revision ID: 003_add_activity_table
Revises: 002_add_transcode_command
Create Date: 2026-06-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "003_add_activity_table"
down_revision = "002_add_transcode_command"
branch_labels = None
deprecated = False


def upgrade():
    op.create_table(
        "activity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("media_file_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["media_file_id"], ["media_files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_activity_id"), "activity", ["id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_activity_id"), table_name="activity")
    op.drop_table("activity")
