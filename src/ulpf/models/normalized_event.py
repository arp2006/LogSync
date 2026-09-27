import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ulpf.models.base import Base, JSONType, UUIDType, utc_now

if TYPE_CHECKING:
    from ulpf.models.job import IngestionJob
    from ulpf.models.raw_event import RawEvent
    from ulpf.models.source import Source


class NormalizedEvent(Base):
    __tablename__ = "normalized_events"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    raw_event_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("raw_events.id"), unique=True, nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("sources.id"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("ingestion_jobs.id"), nullable=False
    )
    ocsf_version: Mapped[str] = mapped_column(Text, nullable=False)
    class_uid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_uid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    severity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    raw_event: Mapped["RawEvent"] = relationship("RawEvent", back_populates="normalized_event")
    source: Mapped["Source"] = relationship("Source", back_populates="normalized_events")
    job: Mapped["IngestionJob"] = relationship("IngestionJob", back_populates="normalized_events")

    __table_args__ = (
        Index("ix_normalized_source_time", "source_id", "event_time"),
        Index("ix_normalized_class_time", "class_uid", "event_time"),
        Index("ix_normalized_event_data", "event_data", postgresql_using="gin"),
    )
