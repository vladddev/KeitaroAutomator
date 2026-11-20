from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthSession(Base):
    """User session storing selected Keitaro API auth mode."""

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    custom_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_hint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Campaign(Base):
    """Local cache and wrapper metadata for Keitaro campaigns."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keitaro_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    alias: Mapped[str | None] = mapped_column(String(255), nullable=True)
    domain_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    traffic_source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_via_wrapper: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class Stream(Base):
    """Keitaro stream synced into wrapper."""

    __tablename__ = "streams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keitaro_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    campaign_keitaro_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stream_type: Mapped[str] = mapped_column(String(64), default="regular", nullable=False)
    schema: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    has_offers: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, nullable=False
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    offers: Mapped[list["StreamOffer"]] = relationship(
        "StreamOffer",
        back_populates="stream",
        cascade="all, delete-orphan",
        order_by="(StreamOffer.sort_order, StreamOffer.id)",
    )


class StreamOffer(Base):
    """Published and draft offer bindings for a stream."""

    __tablename__ = "stream_offers"
    __table_args__ = (UniqueConstraint("stream_id", "offer_keitaro_id", name="uq_stream_offer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stream_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("streams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    offer_keitaro_id: Mapped[int] = mapped_column(Integer, nullable=False)
    offer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    published_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    published_share: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    draft_status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    draft_share: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    draft_is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    stream: Mapped[Stream] = relationship("Stream", back_populates="offers")
