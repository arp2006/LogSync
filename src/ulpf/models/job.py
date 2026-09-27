import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ulpf.models.base import Base, UUIDType, utc_now

if TYPE_CHECKING:
    from ulpf.models.normalized_event import NormalizedEvent
    from ulpf.models.raw_event import RawEvent
    from ulpf.models.source import Source


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("sources.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    input_format: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    raw_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    raw_file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source: Mapped["Source"] = relationship("Source", back_populates="jobs")
    raw_events: Mapped[list["RawEvent"]] = relationship(
        "RawEvent", back_populates="job", cascade="all, delete-orphan"
    )
    normalized_events: Mapped[list["NormalizedEvent"]] = relationship(
        "NormalizedEvent", back_populates="job", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "input_format IN ('cef', 'syslog', 'json')",
            name="ck_ingestion_jobs_input_format",
        ),
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'completed_with_errors', 'failed')",
            name="ck_ingestion_jobs_status",
        ),
        CheckConstraint("raw_file_size >= 0", name="ck_ingestion_jobs_file_size"),
        Index("ix_jobs_queue", "created_at", postgresql_where=(status == "queued")),
        Index("ix_jobs_source_created", "source_id", "created_at"),
    )
