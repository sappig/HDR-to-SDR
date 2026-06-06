"""add queue transcode command

Revision ID: 002_add_transcode_command
Revises: 001_init
Create Date: 2026-06-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "002_add_transcode_command"
down_revision = "001_init"
branch_labels = None
deprecated = False


def upgrade():
    op.add_column("queue", sa.Column("transcode_command", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("queue", "transcode_command")
