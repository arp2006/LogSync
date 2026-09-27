import re
from datetime import UTC, datetime
from typing import Any

from ulpf.parsers.base import ParseContext, ParsedEvent, ParseError, ParseResult


class SyslogParser:
    name = "syslog"
    version = "1.0.0"

    # RFC 5424 header pattern:
    # <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID [SD] MSG
    RFC5424_PATTERN = re.compile(
        r"^<(?P<pri>\d{1,3})>(?P<version>\d+)\s+"
        r"(?P<timestamp>\S+)\s+"
        r"(?P<hostname>\S+)\s+"
        r"(?P<app_name>\S+)\s+"
        r"(?P<proc_id>\S+)\s+"
        r"(?P<msg_id>\S+)\s*"
        r"(?P<structured_data>-(?:\[.*?\])*|\[.*?\])?\s*"
        r"(?P<msg>.*)$",
        re.DOTALL,
    )

    # RFC 3164 pattern:
    # <PRI>Mmm dd hh:mm:ss HOSTNAME TAG: MSG
    RFC3164_PATTERN = re.compile(
        r"^(?:<(?P<pri>\d{1,3})>)?(?P<timestamp>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
        r"(?P<hostname>\S+)\s+"
        r"(?:(?P<tag>[a-zA-Z0-9_\.\-]+)(?:\[(?P<pid>\d+)\])?:\s*)?"
        r"(?P<msg>.*)$",
        re.DOTALL,
    )

    # Common connection pattern in router/firewall messages:
    # e.g. "Denied TCP connection from 10.0.1.25:51514 to 192.0.2.20:443"
    CONN_PATTERN = re.compile(
        r"(?P<action>Denied|Allowed|Accepted|Dropped|Blocked|Reset)\s+"
        r"(?:(?P<proto>[A-Z0-9]+)\s+)?(?:connection\s+)?from\s+"
        r"(?P<src_ip>\d{1,3}(?:\.\d{1,3}){3})(?::(?P<src_port>\d+))?\s+to\s+"
        r"(?P<dst_ip>\d{1,3}(?:\.\d{1,3}){3})(?::(?P<dst_port>\d+))?",
        re.IGNORECASE,
    )

    def _parse_pri(self, pri_str: str | None) -> tuple[int | None, int | None]:
        if not pri_str:
            return None, None
        try:
            pri = int(pri_str)
            facility = pri // 8
            severity = pri % 8
            return facility, severity
        except (ValueError, TypeError):
            return None, None

    def _parse_rfc5424_timestamp(self, ts_str: str) -> datetime | None:
        if ts_str == "-":
            return None
        clean_ts = ts_str[:-1] + "+00:00" if ts_str.endswith("Z") else ts_str
        try:
            dt = datetime.fromisoformat(clean_ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            return None

    def _parse_rfc3164_timestamp(
        self, ts_str: str, context: ParseContext
    ) -> tuple[datetime | None, bool]:
        """
        Parse RFC 3164 timestamp (e.g. 'Sep 27 12:30:15').
        Since RFC 3164 omits year, infer year from context received_at.
        Returns (parsed_datetime, year_was_inferred).
        """
        inferred_year = context.received_at.year
        # Normalise single-digit day spaces e.g. 'Sep  7' -> 'Sep 7'
        normalized = " ".join(ts_str.split())
        full_str = f"{normalized} {inferred_year}"
        try:
            dt = datetime.strptime(full_str, "%b %d %H:%M:%S %Y")
            return dt.replace(tzinfo=UTC), True
        except ValueError:
            return None, False

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

        attributes: dict[str, Any] = {}
        timestamp: datetime | None = None
        severity: int | None = None
        message: str = stripped
        hostname: str | None = None
        app_name: str | None = None

        # 1. Attempt RFC 5424 match
        m5424 = self.RFC5424_PATTERN.match(stripped)
        if m5424:
            attributes["syslog_format"] = "rfc5424"
            facility, severity = self._parse_pri(m5424.group("pri"))
            attributes["facility"] = facility
            attributes["syslog_version"] = m5424.group("version")
            hostname = m5424.group("hostname")
            app_name = m5424.group("app_name")
            proc_id = m5424.group("proc_id")
            msg_id = m5424.group("msg_id")
            sd = m5424.group("structured_data")

            if hostname != "-":
                attributes["hostname"] = hostname
            if app_name != "-":
                attributes["app_name"] = app_name
            if proc_id != "-":
                attributes["proc_id"] = proc_id
            if msg_id != "-":
                attributes["msg_id"] = msg_id
            if sd and sd != "-":
                attributes["structured_data"] = sd

            timestamp = self._parse_rfc5424_timestamp(m5424.group("timestamp"))
            message = m5424.group("msg") or ""

        else:
            # 2. Attempt RFC 3164 match
            m3164 = self.RFC3164_PATTERN.match(stripped)
            if m3164:
                attributes["syslog_format"] = "rfc3164"
                facility, severity = self._parse_pri(m3164.group("pri"))
                attributes["facility"] = facility
                attributes["hostname"] = m3164.group("hostname")
                if m3164.group("tag"):
                    attributes["tag"] = m3164.group("tag")
                if m3164.group("pid"):
                    attributes["pid"] = m3164.group("pid")

                raw_ts = m3164.group("timestamp")
                timestamp, year_inferred = self._parse_rfc3164_timestamp(raw_ts, context)
                if year_inferred:
                    attributes["timestamp_inferred_year"] = True
                    attributes["timestamp_inferred_timezone"] = "UTC"

                message = m3164.group("msg") or ""
            else:
                # Fallback: treat as raw syslog message without structured headers
                attributes["syslog_format"] = "unknown_syslog"
                message = stripped

        # Extract network telemetry from message if present
        src_ip = None
        dst_ip = None
        src_port = None
        dst_port = None
        action = None
        event_name = app_name or "syslog_event"

        conn_match = self.CONN_PATTERN.search(message)
        if conn_match:
            action = conn_match.group("action").lower()
            proto = conn_match.group("proto")
            if proto:
                attributes["protocol"] = proto.upper()
            src_ip = conn_match.group("src_ip")
            dst_ip = conn_match.group("dst_ip")
            if conn_match.group("src_port"):
                src_port = int(conn_match.group("src_port"))
            if conn_match.group("dst_port"):
                dst_port = int(conn_match.group("dst_port"))
            event_name = f"network_{action}"

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
            attributes=attributes,
        )

        return ParseResult(
            event=parsed_event,
            parser_name=self.name,
            parser_version=self.version,
        )
