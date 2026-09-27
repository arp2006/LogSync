import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ulpf.models.base import Base, JSONType, UUIDType, utc_now

if TYPE_CHECKING:
    from ulpf.models.raw_event import RawEvent


class ParserError(Base):
    __tablename__ = "parser_errors"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    raw_event_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("raw_events.id"), nullable=False
    )
    parser_name: Mapped[str] = mapped_column(Text, nullable=False)
    parser_version: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    raw_event: Mapped["RawEvent"] = relationship("RawEvent", back_populates="parser_errors")

    __table_args__ = (
        CheckConstraint(
            "stage IN ('parse', 'normalize', 'validate')",
            name="ck_parser_errors_stage",
        ),
        UniqueConstraint(
            "raw_event_id",
            "parser_name",
            "parser_version",
            "stage",
            name="uq_parser_errors_event_stage",
        ),
        Index("ix_parser_errors_created", "created_at"),
    )
