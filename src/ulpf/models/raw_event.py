import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ulpf.models.base import Base, UUIDType, utc_now

if TYPE_CHECKING:
    from ulpf.models.job import IngestionJob
    from ulpf.models.normalized_event import NormalizedEvent
    from ulpf.models.parser_error import ParserError
    from ulpf.models.source import Source


class RawEvent(Base):
    __tablename__ = "raw_events"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("ingestion_jobs.id"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("sources.id"), nullable=False
    )
    record_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    job: Mapped["IngestionJob"] = relationship("IngestionJob", back_populates="raw_events")
    source: Mapped["Source"] = relationship("Source", back_populates="raw_events")
    normalized_event: Mapped["NormalizedEvent | None"] = relationship(
        "NormalizedEvent", back_populates="raw_event", uselist=False, cascade="all, delete-orphan"
    )
    parser_errors: Mapped[list["ParserError"]] = relationship(
        "ParserError", back_populates="raw_event", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("record_index >= 0", name="ck_raw_events_record_index"),
        UniqueConstraint("job_id", "record_index", name="uq_raw_events_job_record_index"),
        Index("ix_raw_events_source_received", "source_id", "received_at"),
    )
