import uuid
from datetime import UTC, datetime

import pytest

from ulpf.models.source import Source
from ulpf.parsers.base import ParsedEvent
from ulpf.services.normalization import (
    NormalizationError,
    OCSFNormalizer,
)


@pytest.fixture
def mock_source():
    return Source(
        id=uuid.uuid4(),
        name="edge-firewall-01",
        vendor="AcmeNet",
        product="EdgeFirewall",
        is_active=True,
    )


def test_normalizer_network_activity_event(mock_source):
    normalizer = OCSFNormalizer()
    parsed = ParsedEvent(
        timestamp=datetime(2026, 9, 27, 12, 30, 15, tzinfo=UTC),
        event_name="Connection allowed",
        severity=3,
        source_ip="10.0.1.25",
        destination_ip="192.0.2.20",
        source_port=51514,
        destination_port=443,
        action="allow",
        message="Connection permitted by rule 42",
        attributes={"rule_id": "42", "custom_tag": "internal_traffic"},
    )

    res = normalizer.normalize(
        parsed=parsed,
        source=mock_source,
        raw_event_id=str(uuid.uuid4()),
        raw_sha256="a" * 64,
        storage_ref="data/raw/2026/09/job/original.bin",
        parser_name="cef",
        parser_version="1.0.0",
    )

    assert res.class_uid == 4001
    assert res.category_uid == 4
    assert res.severity_id == 1  # Low
    assert res.event_data["schema"]["name"] == "OCSF"
    assert res.event_data["raw"]["sha256"] == "a" * 64
    assert res.event_data["ocsf"]["action"] == "allow"
    assert res.event_data["ocsf"]["src_endpoint"]["ip"] == "10.0.1.25"
    assert res.event_data["ocsf"]["src_endpoint"]["port"] == 51514
    assert res.event_data["ocsf"]["dst_endpoint"]["ip"] == "192.0.2.20"
    # Unmapped fields are preserved
    assert res.event_data["ocsf"]["unmapped"]["rule_id"] == "42"
    assert res.event_data["ocsf"]["unmapped"]["custom_tag"] == "internal_traffic"


def test_normalizer_auth_event(mock_source):
    normalizer = OCSFNormalizer()
    parsed = ParsedEvent(
        timestamp=datetime(2026, 9, 27, 12, 31, 0, tzinfo=UTC),
        event_name="authentication_failed",
        severity="High",
        source_ip="198.51.100.44",
        action="deny",
        attributes={"username": "alice", "auth_protocol": "radius"},
    )

    res = normalizer.normalize(
        parsed=parsed,
        source=mock_source,
        raw_event_id=str(uuid.uuid4()),
        raw_sha256="b" * 64,
        storage_ref="data/raw/2026/09/job/original.bin",
        parser_name="json",
        parser_version="1.0.0",
    )

    assert res.class_uid == 3001
    assert res.category_uid == 3
    assert res.severity_id == 3  # High
    assert res.event_data["ocsf"]["user"]["name"] == "alice"
    assert res.event_data["ocsf"]["src_endpoint"]["ip"] == "198.51.100.44"
    assert res.event_data["ocsf"]["unmapped"]["auth_protocol"] == "radius"


def test_normalizer_invalid_ip_raises_error(mock_source):
    normalizer = OCSFNormalizer()
    parsed = ParsedEvent(
        source_ip="999.999.999.999",  # Invalid IPv4
        destination_ip="10.0.0.1",
        action="allow",
    )

    with pytest.raises(NormalizationError) as exc_info:
        normalizer.normalize(
            parsed=parsed,
            source=mock_source,
            raw_event_id=str(uuid.uuid4()),
            raw_sha256="c" * 64,
            storage_ref="dummy_path",
            parser_name="cef",
            parser_version="1.0.0",
        )
    assert exc_info.value.error_code == "INVALID_IP_ADDRESS"


def test_normalizer_invalid_port_raises_error(mock_source):
    normalizer = OCSFNormalizer()
    parsed = ParsedEvent(
        source_ip="10.0.0.1",
        source_port=70000,  # Invalid port > 65535
        action="allow",
    )

    with pytest.raises(NormalizationError) as exc_info:
        normalizer.normalize(
            parsed=parsed,
            source=mock_source,
            raw_event_id=str(uuid.uuid4()),
            raw_sha256="d" * 64,
            storage_ref="dummy_path",
            parser_name="cef",
            parser_version="1.0.0",
        )
    assert exc_info.value.error_code == "INVALID_PORT_RANGE"
