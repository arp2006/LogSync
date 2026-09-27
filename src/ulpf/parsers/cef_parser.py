import re
from datetime import UTC, datetime
from typing import Any

from ulpf.parsers.base import ParseContext, ParsedEvent, ParseError, ParseResult


class CEFParser:
    name = "cef"
    version = "1.0.0"

    # Regex to tokenize extension key=value pairs:
    # A key consists of alphanumeric characters without spaces followed by '='
    EXT_KEY_PATTERN = re.compile(r"([a-zA-Z0-9_\.\-]+)=")

    def _split_unescaped_pipes(self, text: str, max_splits: int = 7) -> list[str]:
        """
        Split string on unescaped pipe '|' characters up to max_splits times.
        Handles '\\|' escaping.
        """
        parts = []
        current = []
        i = 0
        n = len(text)
        splits = 0

        while i < n:
            char = text[i]
            if char == "\\" and i + 1 < n:
                # Escaped character
                next_char = text[i + 1]
                if next_char == "|" or next_char == "\\":
                    current.append(next_char)
                    i += 2
                    continue
                else:
                    current.append(char)
                    i += 1
                    continue
            elif char == "|" and splits < max_splits:
                parts.append("".join(current))
                current = []
                splits += 1
                i += 1
                continue
            else:
                current.append(char)
                i += 1

        parts.append("".join(current))
        return parts

    def _parse_extension(self, ext_str: str) -> dict[str, str]:
        """
        Parse CEF extension into key-value dictionary respecting spaces and escaped equals.
        """
        if not ext_str.strip():
            return {}

        results = {}
        # Find all key= matches and their positions
        matches = list(self.EXT_KEY_PATTERN.finditer(ext_str))
        if not matches:
            return {"raw_extension": ext_str.strip()}

        for idx, match in enumerate(matches):
            key = match.group(1)
            val_start = match.end()
            if idx + 1 < len(matches):
                val_end = matches[idx + 1].start()
            else:
                val_end = len(ext_str)

            raw_val = ext_str[val_start:val_end].strip()
            # Unescape \=, \\, \n, \r, and \ (escaped space)
            clean_val = (
                raw_val.replace("\\=", "=")
                .replace("\\ ", " ")
                .replace("\\\\", "\\")
                .replace("\\n", "\n")
                .replace("\\r", "\r")
            )
            results[key] = clean_val

        return results

    def _parse_timestamp(self, val: str | None) -> datetime | None:
        if not val:
            return None
        val_clean = val.strip()
        # Epoch ms or seconds
        if val_clean.isdigit():
            epoch = int(val_clean)
            if epoch > 1e11:  # ms
                epoch = epoch / 1000.0
            return datetime.fromtimestamp(epoch, tz=UTC)

        # Try ISO format
        try:
            iso_val = val_clean[:-1] + "+00:00" if val_clean.endswith("Z") else val_clean
            dt = datetime.fromisoformat(iso_val)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            pass

        # Try common Syslog / CEF timestamp formats: e.g. "Sep 27 2026 12:30:15"
        for fmt in (
            "%b %d %Y %H:%M:%S",
            "%b %d %Y %H:%M:%S %Z",
            "%b %d %H:%M:%S %Y",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(val_clean, fmt)
                return dt.replace(tzinfo=UTC)
            except ValueError:
                continue

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

        if not stripped.startswith("CEF:"):
            raise ParseError(
                message="Record does not start with CEF: prefix",
                error_code="CEF_MISSING_PREFIX",
            )

        # Split into at most 8 parts:
        # [0: CEF:Version, 1: Vendor, 2: Product, 3: Version,
        #  4: SignatureID, 5: Name, 6: Severity, 7: Extension]
        parts = self._split_unescaped_pipes(stripped, max_splits=7)
        if len(parts) < 7:
            raise ParseError(
                message=f"Expected at least 7 CEF header fields, got {len(parts)}",
                error_code="CEF_INVALID_HEADER",
                details={"fields_count": len(parts)},
            )

        cef_version_prefix = parts[0]
        vendor = parts[1]
        product = parts[2]
        dev_version = parts[3]
        signature_id = parts[4]
        name = parts[5]
        severity = parts[6]
        extension_str = parts[7] if len(parts) > 7 else ""

        extension = self._parse_extension(extension_str)

        # Extract standard fields
        src_ip = extension.pop("src", None) or extension.pop("sourceAddress", None)
        dst_ip = extension.pop("dst", None) or extension.pop("destinationAddress", None)
        src_port = self._parse_int(extension.pop("spt", None) or extension.pop("sourcePort", None))
        dst_port = self._parse_int(
            extension.pop("dpt", None) or extension.pop("destinationPort", None)
        )
        action = extension.pop("act", None) or extension.pop("deviceAction", None)
        message = extension.pop("msg", None) or extension.pop("message", None)

        raw_time = (
            extension.pop("rt", None)
            or extension.pop("deviceReceiptTime", None)
            or extension.pop("end", None)
            or extension.pop("start", None)
        )
        timestamp = self._parse_timestamp(raw_time)

        # Retain header values and unmapped extension fields in attributes
        attributes = dict(extension)
        attributes["cef_version"] = cef_version_prefix.replace("CEF:", "")
        attributes["device_vendor"] = vendor
        attributes["device_product"] = product
        attributes["device_version"] = dev_version
        attributes["device_event_class_id"] = signature_id
        if raw_time and not timestamp:
            attributes["raw_time"] = raw_time

        parsed_event = ParsedEvent(
            timestamp=timestamp,
            event_name=name,
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
