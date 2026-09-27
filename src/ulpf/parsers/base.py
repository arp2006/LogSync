from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


class ParseError(Exception):
    """Raised when a log line cannot be parsed by the selected parser."""

    def __init__(
        self,
        message: str,
        error_code: str = "PARSE_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


@dataclass(frozen=True)
class ParseContext:
    source_id: str
    job_id: str
    record_index: int
    received_at: datetime


@dataclass
class ParsedEvent:
    timestamp: datetime | None = None
    event_name: str | None = None
    severity: str | int | None = None
    source_ip: str | None = None
    destination_ip: str | None = None
    source_port: int | None = None
    destination_port: int | None = None
    action: str | None = None
    message: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParseResult:
    event: ParsedEvent
    parser_name: str
    parser_version: str


class LogParser(Protocol):
    name: str
    version: str

    def parse(self, raw: bytes, context: ParseContext) -> ParseResult: ...
