"""initial schema

Revision ID: 001_init
Revises: 
Create Date: 2026-05-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "001_init"
down_revision = None
branch_labels = None
deprecated = False


def upgrade():
    op.create_table(
        "folders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path"),
    )
    op.create_index(op.f("ix_folders_id"), "folders", ["id"], unique=False)

    op.create_table(
        "media_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("folder_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("resolution", sa.String(), nullable=True),
        sa.Column("codec", sa.String(), nullable=True),
        sa.Column("bitrate", sa.Integer(), nullable=True),
        sa.Column("audio_tracks", sa.Integer(), nullable=True),
        sa.Column("subtitle_tracks", sa.Integer(), nullable=True),
        sa.Column("hdr_detected", sa.Boolean(), nullable=False),
        sa.Column("hdr_type", sa.String(), nullable=True),
        sa.Column("scanned_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("scan_error", sa.Text(), nullable=True),
        sa.Column("output_path", sa.String(), nullable=True),
        sa.Column("extra_metadata", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["folder_id"], ["folders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path"),
    )
    op.create_index(op.f("ix_media_files_id"), "media_files", ["id"], unique=False)

    op.create_table(
        "queue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("media_file_id", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("eta_seconds", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("log_path", sa.String(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["media_file_id"], ["media_files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_queue_id"), "queue", ["id"], unique=False)

    op.create_table(
        "transcode_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("media_file_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("result", sa.String(), nullable=True),
        sa.Column("log", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["media_file_id"], ["media_files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transcode_history_id"), "transcode_history", ["id"], unique=False)

    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(op.f("ix_app_settings_id"), "app_settings", ["id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_app_settings_id"), table_name="app_settings")
    op.drop_table("app_settings")
    op.drop_index(op.f("ix_transcode_history_id"), table_name="transcode_history")
    op.drop_table("transcode_history")
    op.drop_index(op.f("ix_queue_id"), table_name="queue")
    op.drop_table("queue")
    op.drop_index(op.f("ix_media_files_id"), table_name="media_files")
    op.drop_table("media_files")
    op.drop_index(op.f("ix_folders_id"), table_name="folders")
    op.drop_table("folders")
