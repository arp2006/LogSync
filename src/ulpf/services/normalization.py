import ipaddress
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ulpf.models.source import Source
from ulpf.parsers.base import ParsedEvent


class NormalizationError(Exception):
    def __init__(self, message: str, error_code: str = "NORMALIZATION_ERROR"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class OCSFSchemaValidator:
    def __init__(self, schema_path: Path | str | None = None) -> None:
        path = (
            Path(schema_path)
            if schema_path
            else Path(__file__).resolve().parent.parent.parent / "schemas" / "ocsf" / "schema.json"
        )
        if not path.exists():
            # Fallback relative to project root
            path = Path("schemas/ocsf/schema.json")
        with open(path, encoding="utf-8") as f:
            self._schema = json.load(f)

    @property
    def version(self) -> str:
        return self._schema.get("version", "1.1.0")

    def validate_ip(self, ip_str: str | None) -> bool:
        if not ip_str:
            return True
        try:
            ipaddress.ip_address(ip_str)
            return True
        except ValueError:
            return False

    def validate_port(self, port: int | None) -> bool:
        if port is None:
            return True
        return 0 <= port <= 65535

    def validate(self, ocsf_event: dict[str, Any]) -> None:
        class_uid = str(ocsf_event.get("class_uid"))
        classes = self._schema.get("classes", {})
        if class_uid not in classes:
            raise NormalizationError(
                f"Unknown OCSF class_uid: {class_uid}",
                error_code="INVALID_CLASS_UID",
            )

        class_def = classes[class_uid]
        for req in class_def.get("required_fields", []):
            if req not in ocsf_event or ocsf_event[req] is None:
                raise NormalizationError(
                    f"Missing required OCSF field: '{req}' for class {class_uid}",
                    error_code="MISSING_REQUIRED_FIELD",
                )

        # Validate endpoints if present
        src_ep = ocsf_event.get("src_endpoint")
        if src_ep and "ip" in src_ep and not self.validate_ip(src_ep["ip"]):
            raise NormalizationError(
                f"Invalid source IP address format: {src_ep['ip']}",
                error_code="INVALID_IP_ADDRESS",
            )
        if src_ep and "port" in src_ep and not self.validate_port(src_ep["port"]):
            raise NormalizationError(
                f"Invalid source port range: {src_ep['port']}",
                error_code="INVALID_PORT_RANGE",
            )

        dst_ep = ocsf_event.get("dst_endpoint")
        if dst_ep and "ip" in dst_ep and not self.validate_ip(dst_ep["ip"]):
            raise NormalizationError(
                f"Invalid destination IP address format: {dst_ep['ip']}",
                error_code="INVALID_IP_ADDRESS",
            )
        if dst_ep and "port" in dst_ep and not self.validate_port(dst_ep["port"]):
            raise NormalizationError(
                f"Invalid destination port range: {dst_ep['port']}",
                error_code="INVALID_PORT_RANGE",
            )


@dataclass(frozen=True)
class NormalizedResult:
    class_uid: int
    category_uid: int
    activity_id: int
    severity_id: int
    event_time: datetime
    event_data: dict[str, Any]
    ocsf_version: str


class OCSFNormalizer:
    def __init__(self, validator: OCSFSchemaValidator | None = None) -> None:
        self.validator = validator or OCSFSchemaValidator()

    def _map_action(self, action_str: str | None) -> tuple[str, int]:
        if not action_str:
            return "unknown", 0
        clean = action_str.strip().lower()
        if clean in ("allow", "allowed", "accept", "accepted", "permit", "pass"):
            return "allow", 1
        elif clean in ("deny", "denied", "block", "blocked", "drop", "dropped", "reject"):
            return "deny", 2
        elif clean in ("reset", "rst", "abort"):
            return "reset", 3
        return "unknown", 0

    def _map_severity(self, raw_sev: Any) -> tuple[str, int]:
        if raw_sev is None:
            return "Unknown", 0

        # Numeric severity
        try:
            num = int(raw_sev)
            if num <= 0:
                return "Unknown", 0
            elif num <= 3:
                return "Low", 1
            elif num <= 6:
                return "Medium", 2
            elif num <= 8:
                return "High", 3
            else:
                return "Critical", 4
        except (ValueError, TypeError):
            pass

        # Text severity
        sev_str = str(raw_sev).strip().lower()
        if sev_str in ("low", "info", "informational", "debug", "notice"):
            return "Low", 1
        elif sev_str in ("medium", "med", "warn", "warning"):
            return "Medium", 2
        elif sev_str in ("high", "err", "error"):
            return "High", 3
        elif sev_str in ("critical", "crit", "fatal", "emerg", "emergency", "alert"):
            return "Critical", 4

        return "Unknown", 0

    def normalize(
        self,
        parsed: ParsedEvent,
        *,
        source: Source,
        raw_event_id: str,
        raw_sha256: str,
        storage_ref: str,
        parser_name: str,
        parser_version: str,
        received_at: datetime | None = None,
    ) -> NormalizedResult:
        # Standardize timestamp or fallback to received_at / current UTC
        event_time = parsed.timestamp or received_at or datetime.now(UTC)
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=UTC)
        iso_time = event_time.isoformat()

        action_name, action_id = self._map_action(parsed.action)
        severity_label, severity_id = self._map_severity(parsed.severity)

        # Determine OCSF class:
        # If there are network endpoints or action, classify as 4001 (Network Activity)
        has_network = bool(
            parsed.source_ip
            or parsed.destination_ip
            or parsed.source_port
            or parsed.destination_port
            or parsed.action
        )
        is_auth = (
            "auth" in (parsed.event_name or "").lower()
            or "login" in (parsed.event_name or "").lower()
        )

        unmapped = dict(parsed.attributes)

        if has_network and not is_auth:
            class_uid = 4001
            category_uid = 4
            category_name = "Network Activity"
            activity_id = action_id
            activity_name = parsed.event_name or "Network Connection"

            src_endpoint = {}
            if parsed.source_ip:
                src_endpoint["ip"] = parsed.source_ip
            if parsed.source_port is not None:
                src_endpoint["port"] = parsed.source_port

            dst_endpoint = {}
            if parsed.destination_ip:
                dst_endpoint["ip"] = parsed.destination_ip
            if parsed.destination_port is not None:
                dst_endpoint["port"] = parsed.destination_port

            ocsf_data = {
                "class_uid": class_uid,
                "category_uid": category_uid,
                "category_name": category_name,
                "activity_id": activity_id,
                "activity_name": activity_name,
                "time": iso_time,
                "action": action_name,
                "action_id": action_id,
                "severity": severity_label,
                "severity_id": severity_id,
                "metadata": {
                    "version": self.validator.version,
                    "product": {
                        "vendor_name": source.vendor or "Unknown",
                        "name": source.product or source.name,
                    },
                },
                "src_endpoint": src_endpoint,
                "dst_endpoint": dst_endpoint,
                "unmapped": unmapped,
            }
        elif is_auth:
            class_uid = 3001
            category_uid = 3
            category_name = "Identity & Access Management"
            activity_id = 1
            activity_name = "Authentication"

            user_obj = {}
            if "username" in unmapped:
                user_obj["name"] = unmapped.pop("username")
            elif "user" in unmapped:
                user_obj["name"] = unmapped.pop("user")

            src_endpoint = {}
            if parsed.source_ip:
                src_endpoint["ip"] = parsed.source_ip

            ocsf_data = {
                "class_uid": class_uid,
                "category_uid": category_uid,
                "category_name": category_name,
                "activity_id": activity_id,
                "activity_name": activity_name,
                "time": iso_time,
                "action": action_name,
                "action_id": action_id,
                "severity": severity_label,
                "severity_id": severity_id,
                "user": user_obj,
                "src_endpoint": src_endpoint,
                "metadata": {
                    "version": self.validator.version,
                    "product": {
                        "vendor_name": source.vendor or "Unknown",
                        "name": source.product or source.name,
                    },
                },
                "unmapped": unmapped,
            }
        else:
            class_uid = 1001
            category_uid = 1
            category_name = "System Activity"
            activity_id = 99
            activity_name = parsed.event_name or "Generic Event"

            ocsf_data = {
                "class_uid": class_uid,
                "category_uid": category_uid,
                "category_name": category_name,
                "activity_id": activity_id,
                "activity_name": activity_name,
                "time": iso_time,
                "message": parsed.message or "",
                "severity": severity_label,
                "severity_id": severity_id,
                "metadata": {
                    "version": self.validator.version,
                    "product": {
                        "vendor_name": source.vendor or "Unknown",
                        "name": source.product or source.name,
                    },
                },
                "unmapped": unmapped,
            }

        # Build full ULPF canonical envelope with forensic traceability
        canonical_envelope = {
            "schema": {
                "name": "OCSF",
                "version": self.validator.version,
            },
            "source": {
                "source_id": str(source.id),
                "name": source.name,
                "vendor": source.vendor,
                "product": source.product,
            },
            "raw": {
                "raw_event_id": str(raw_event_id),
                "sha256": raw_sha256,
                "storage_ref": storage_ref,
            },
            "processing": {
                "parser": parser_name,
                "parser_version": parser_version,
                "status": "normalized",
            },
            "ocsf": ocsf_data,
        }

        # Validate against pinned schema
        self.validator.validate(ocsf_data)

        return NormalizedResult(
            class_uid=class_uid,
            category_uid=category_uid,
            activity_id=activity_id,
            severity_id=severity_id,
            event_time=event_time,
            event_data=canonical_envelope,
            ocsf_version=self.validator.version,
        )
