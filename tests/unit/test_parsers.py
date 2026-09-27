from datetime import UTC, datetime

import pytest

from ulpf.parsers.base import ParseContext, ParseError
from ulpf.parsers.cef_parser import CEFParser
from ulpf.parsers.json_parser import JSONParser
from ulpf.parsers.registry import create_default_registry
from ulpf.parsers.syslog_parser import SyslogParser


@pytest.fixture
def parse_context():
    return ParseContext(
        source_id="test-source-id",
        job_id="test-job-id",
        record_index=0,
        received_at=datetime(2026, 9, 27, 12, 0, 0, tzinfo=UTC),
    )


# ------------------- JSON Parser Tests -------------------


def test_json_parser_valid_record(parse_context):
    parser = JSONParser()
    raw = (
        b'{"timestamp": "2026-09-27T12:31:00Z", "device": "vpn-gateway-01", '
        b'"event": "authentication_failed", "username": "test-user", '
        b'"src_ip": "198.51.100.44", "dst_ip": "10.0.0.1", "src_port": 50000, '
        b'"dst_port": 443, "action": "deny", "reason": "invalid_credentials"}'
    )
    result = parser.parse(raw, parse_context)

    event = result.event
    assert event.source_ip == "198.51.100.44"
    assert event.destination_ip == "10.0.0.1"
    assert event.source_port == 50000
    assert event.destination_port == 443
    assert event.action == "deny"
    assert event.event_name == "authentication_failed"
    assert event.message == "invalid_credentials"
    assert event.timestamp == datetime(2026, 9, 27, 12, 31, 0, tzinfo=UTC)
    # Check that unmapped fields are preserved
    assert event.attributes["device"] == "vpn-gateway-01"
    assert event.attributes["username"] == "test-user"


def test_json_parser_non_object(parse_context):
    parser = JSONParser()
    with pytest.raises(ParseError) as exc_info:
        parser.parse(b'["list", "not", "object"]', parse_context)
    assert exc_info.value.error_code == "JSON_NOT_OBJECT"


def test_json_parser_malformed_syntax(parse_context):
    parser = JSONParser()
    with pytest.raises(ParseError) as exc_info:
        parser.parse(b'{"key": "unclosed string', parse_context)
    assert exc_info.value.error_code == "JSON_SYNTAX_ERROR"


# ------------------- CEF Parser Tests -------------------


def test_cef_parser_valid_record(parse_context):
    parser = CEFParser()
    raw = (
        b"CEF:0|AcmeNet|EdgeFirewall|4.2|ALLOW-001|Connection allowed|3|"
        b"src=10.0.1.25 spt=51514 dst=192.0.2.20 dpt=443 proto=TCP act=allow"
    )
    result = parser.parse(raw, parse_context)

    event = result.event
    assert event.event_name == "Connection allowed"
    assert event.severity == "3"
    assert event.source_ip == "10.0.1.25"
    assert event.source_port == 51514
    assert event.destination_ip == "192.0.2.20"
    assert event.destination_port == 443
    assert event.action == "allow"
    # Unmapped extension preserved in attributes
    assert event.attributes["proto"] == "TCP"
    assert event.attributes["device_vendor"] == "AcmeNet"
    assert event.attributes["device_product"] == "EdgeFirewall"
    assert event.attributes["device_event_class_id"] == "ALLOW-001"


def test_cef_parser_escaped_delimiters(parse_context):
    parser = CEFParser()
    # Vendor has escaped pipe 'Acme\|Corp' and extension has escaped '='
    raw = (
        b"CEF:0|Acme\\|Corp|EdgeFirewall|4.2|100|Event\\|Name|5|"
        b"src=1.2.3.4 msg=Key\\=Value\\ testing proto=UDP"
    )
    result = parser.parse(raw, parse_context)
    event = result.event
    assert event.source_ip == "1.2.3.4"
    assert event.attributes["device_vendor"] == "Acme|Corp"
    assert event.event_name == "Event|Name"
    assert event.message == "Key=Value testing"
    assert event.attributes["proto"] == "UDP"


def test_cef_parser_malformed_header(parse_context):
    parser = CEFParser()
    # Only 4 fields instead of 7
    raw = b"CEF:0|AcmeNet|EdgeFirewall|4.2"
    with pytest.raises(ParseError) as exc_info:
        parser.parse(raw, parse_context)
    assert exc_info.value.error_code == "CEF_INVALID_HEADER"


def test_cef_parser_missing_prefix(parse_context):
    parser = CEFParser()
    with pytest.raises(ParseError) as exc_info:
        parser.parse(b"NOT_CEF:0|AcmeNet|Firewall", parse_context)
    assert exc_info.value.error_code == "CEF_MISSING_PREFIX"


# ------------------- Syslog Parser Tests -------------------


def test_syslog_parser_rfc5424(parse_context):
    parser = SyslogParser()
    raw = (
        b"<134>1 2026-09-27T12:30:15Z edge-router-01 routerd 712 - - "
        b"Denied TCP connection from 10.0.1.25:51514 to 192.0.2.20:443"
    )
    result = parser.parse(raw, parse_context)
    event = result.event

    assert event.timestamp == datetime(2026, 9, 27, 12, 30, 15, tzinfo=UTC)
    assert event.source_ip == "10.0.1.25"
    assert event.source_port == 51514
    assert event.destination_ip == "192.0.2.20"
    assert event.destination_port == 443
    assert event.action == "denied"
    assert event.attributes["syslog_format"] == "rfc5424"
    assert event.attributes["hostname"] == "edge-router-01"
    assert event.attributes["app_name"] == "routerd"
    assert event.attributes["proc_id"] == "712"
    assert event.attributes["protocol"] == "TCP"
    # PRI 134: 134 // 8 = 16 (local0), 134 % 8 = 6 (informational)
    assert event.attributes["facility"] == 16
    assert event.severity == 6


def test_syslog_parser_rfc3164_inferred_year(parse_context):
    parser = SyslogParser()
    raw = (
        b"<34>Sep 27 12:30:15 edge-router-01 routerd[712]: "
        b"Denied TCP connection from 10.0.1.25:51514 to 192.0.2.20:443"
    )
    result = parser.parse(raw, parse_context)
    event = result.event

    assert event.timestamp == datetime(2026, 9, 27, 12, 30, 15, tzinfo=UTC)
    assert event.attributes["syslog_format"] == "rfc3164"
    assert event.attributes["timestamp_inferred_year"] is True
    assert event.attributes["timestamp_inferred_timezone"] == "UTC"
    assert event.source_ip == "10.0.1.25"
    assert event.destination_ip == "192.0.2.20"
    assert event.action == "denied"


# ------------------- Registry Tests -------------------


def test_parser_registry():
    registry = create_default_registry()
    assert "cef" in registry.supported_formats()
    assert "syslog" in registry.supported_formats()
    assert "json" in registry.supported_formats()

    # Case-insensitive resolution
    assert isinstance(registry.get("CEF"), CEFParser)
    assert isinstance(registry.get("Json"), JSONParser)
    assert isinstance(registry.get("SYSLOG"), SyslogParser)

    with pytest.raises(ValueError, match="Unsupported input format"):
        registry.get("unknown_format_xyz")
