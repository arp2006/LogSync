from datetime import UTC, datetime

from sqlalchemy import Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import JSON


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


# Type helper for JSON/JSONB compatibility across PostgreSQL and SQLite (for tests)
JSONType = JSON().with_variant(JSONB, "postgresql")
UUIDType = Uuid(as_uuid=True)
