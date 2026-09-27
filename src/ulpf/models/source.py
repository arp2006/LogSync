import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ulpf.models.base import Base, JSONType, UUIDType, utc_now

if TYPE_CHECKING:
    from ulpf.models.job import IngestionJob
    from ulpf.models.normalized_event import NormalizedEvent
    from ulpf.models.raw_event import RawEvent


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False, default="network_device")
    vendor: Mapped[str | None] = mapped_column(Text, nullable=True)
    product: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    jobs: Mapped[list["IngestionJob"]] = relationship(
        "IngestionJob", back_populates="source", cascade="all, delete-orphan"
    )
    raw_events: Mapped[list["RawEvent"]] = relationship(
        "RawEvent", back_populates="source", cascade="all, delete-orphan"
    )
    normalized_events: Mapped[list["NormalizedEvent"]] = relationship(
        "NormalizedEvent", back_populates="source", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("uq_sources_name", func.lower(name), unique=True),
    )
