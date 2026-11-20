"""Initial database schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("custom_api_key", sa.Text(), nullable=True),
        sa.Column("key_hint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("keitaro_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=True),
        sa.Column("domain_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("traffic_source_id", sa.Integer(), nullable=True),
        sa.Column("created_via_wrapper", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_campaigns_keitaro_id", "campaigns", ["keitaro_id"], unique=True)

    op.create_table(
        "streams",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("keitaro_id", sa.Integer(), nullable=False),
        sa.Column("campaign_keitaro_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("stream_type", sa.String(length=64), nullable=False),
        sa.Column("schema", sa.String(length=64), nullable=False),
        sa.Column("has_offers", sa.Boolean(), nullable=False),
        sa.Column(
            "raw_payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_streams_keitaro_id", "streams", ["keitaro_id"], unique=True)
    op.create_index("ix_streams_campaign_keitaro_id", "streams", ["campaign_keitaro_id"])

    op.create_table(
        "stream_offers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "stream_id",
            sa.Integer(),
            sa.ForeignKey("streams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("offer_keitaro_id", sa.Integer(), nullable=False),
        sa.Column("offer_name", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("published_status", sa.String(length=16), nullable=True),
        sa.Column("published_share", sa.Integer(), nullable=True),
        sa.Column("published_is_pinned", sa.Boolean(), nullable=False),
        sa.Column("draft_status", sa.String(length=16), nullable=False),
        sa.Column("draft_share", sa.Integer(), nullable=False),
        sa.Column("draft_is_pinned", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("stream_id", "offer_keitaro_id", name="uq_stream_offer"),
    )
    op.create_index("ix_stream_offers_stream_id", "stream_offers", ["stream_id"])


def downgrade() -> None:
    op.drop_index("ix_stream_offers_stream_id", table_name="stream_offers")
    op.drop_table("stream_offers")
    op.drop_index("ix_streams_campaign_keitaro_id", table_name="streams")
    op.drop_index("ix_streams_keitaro_id", table_name="streams")
    op.drop_table("streams")
    op.drop_index("ix_campaigns_keitaro_id", table_name="campaigns")
    op.drop_table("campaigns")
    op.drop_table("auth_sessions")
