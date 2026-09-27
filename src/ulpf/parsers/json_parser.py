import json
from datetime import UTC, datetime
from typing import Any

from ulpf.parsers.base import ParseContext, ParsedEvent, ParseError, ParseResult


class JSONParser:
    name = "json"
    version = "1.0.0"

    TIMESTAMP_KEYS = ("timestamp", "time", "@timestamp", "event_time", "datetime")
    SRC_IP_KEYS = ("src_ip", "src", "source_ip", "sourceAddress", "client_ip")
    DST_IP_KEYS = ("dst_ip", "dst", "destination_ip", "destinationAddress", "server_ip")
    SRC_PORT_KEYS = ("src_port", "spt", "sourcePort", "source_port")
    DST_PORT_KEYS = ("dst_port", "dpt", "destinationPort", "destination_port")
    ACTION_KEYS = ("action", "act", "activity")
    EVENT_NAME_KEYS = ("event", "event_name", "name", "event_type")
    SEVERITY_KEYS = ("severity", "level", "priority")
    MESSAGE_KEYS = ("message", "msg", "reason", "description")

    def _parse_timestamp(self, val: Any) -> datetime | None:
        if isinstance(val, (int, float)):
            # Epoch timestamp in seconds or milliseconds
            if val > 1e11:  # milliseconds
                val = val / 1000.0
            return datetime.fromtimestamp(val, tz=UTC)
        if isinstance(val, str):
            clean_str = val.strip()
            # Try ISO 8601 parsing
            try:
                # Handle Z notation in fromisoformat
                if clean_str.endswith("Z"):
                    clean_str = clean_str[:-1] + "+00:00"
                dt = datetime.fromisoformat(clean_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            except ValueError:
                return None
        return None

    def _parse_int(self, val: Any) -> int | None:
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    def parse(self, raw: bytes, context: ParseContext) -> ParseResult:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as err:
            raise ParseError(
                message=f"Invalid UTF-8 encoding: {err}",
                error_code="INVALID_ENCODING",
            ) from err

        stripped = text.strip()
        if not stripped:
            raise ParseError(
                message="Empty record",
                error_code="EMPTY_RECORD",
            )

        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as err:
            raise ParseError(
                message=f"JSON syntax error: {err.msg} at line {err.lineno} col {err.colno}",
                error_code="JSON_SYNTAX_ERROR",
                details={"lineno": err.lineno, "colno": err.colno},
            ) from err

        if not isinstance(data, dict):
            raise ParseError(
                message=f"Expected JSON object, got {type(data).__name__}",
                error_code="JSON_NOT_OBJECT",
            )

        extracted = dict(data)  # shallow copy to peel off extracted fields

        # 1. Timestamp
        timestamp = None
        for key in self.TIMESTAMP_KEYS:
            if key in extracted:
                timestamp = self._parse_timestamp(extracted[key])
                break

        # 2. Source IP
        src_ip = None
        for key in self.SRC_IP_KEYS:
            if key in extracted and isinstance(extracted[key], str):
                src_ip = extracted.pop(key)
                break

        # 3. Destination IP
        dst_ip = None
        for key in self.DST_IP_KEYS:
            if key in extracted and isinstance(extracted[key], str):
                dst_ip = extracted.pop(key)
                break

        # 4. Source Port
        src_port = None
        for key in self.SRC_PORT_KEYS:
            if key in extracted:
                src_port = self._parse_int(extracted.pop(key))
                break

        # 5. Destination Port
        dst_port = None
        for key in self.DST_PORT_KEYS:
            if key in extracted:
                dst_port = self._parse_int(extracted.pop(key))
                break

        # 6. Action
        action = None
        for key in self.ACTION_KEYS:
            if key in extracted and isinstance(extracted[key], str):
                action = extracted.pop(key)
                break

        # 7. Event name
        event_name = None
        for key in self.EVENT_NAME_KEYS:
            if key in extracted and isinstance(extracted[key], str):
                event_name = extracted.pop(key)
                break

        # 8. Severity
        severity = None
        for key in self.SEVERITY_KEYS:
            if key in extracted:
                severity = extracted.pop(key)
                break

        # 9. Message
        message = None
        for key in self.MESSAGE_KEYS:
            if key in extracted and isinstance(extracted[key], str):
                message = extracted.pop(key)
                break

        # Any remaining attributes are retained (lossless preservation)
        parsed_event = ParsedEvent(
            timestamp=timestamp,
            event_name=event_name,
            severity=severity,
            source_ip=src_ip,
            destination_ip=dst_ip,
            source_port=src_port,
            destination_port=dst_port,
            action=action,
            message=message,
            attributes=extracted,
        )

        return ParseResult(
            event=parsed_event,
            parser_name=self.name,
            parser_version=self.version,
        )
