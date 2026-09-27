import io
import uuid

import pytest
from sqlalchemy.orm import Session

from ulpf.api.errors import APIError
from ulpf.models.audit_event import AuditEvent
from ulpf.services.evidence_store import EvidenceStore
from ulpf.services.ingestion_service import IngestionService


def test_create_source_success(db_session: Session, evidence_store: EvidenceStore):
    service = IngestionService(evidence_store=evidence_store)
    source = service.create_source(
        db=db_session,
        name="edge-fw-01",
        vendor="AcmeNet",
        product="EdgeFirewall",
        description="Edge firewall for perimeter",
        config={"interface": "eth0"},
    )

    assert source.id is not None
    assert source.name == "edge-fw-01"
    assert source.is_active is True
    assert source.vendor == "AcmeNet"

    # Check audit log
    audit = db_session.query(AuditEvent).filter_by(resource_id=source.id).first()
    assert audit is not None
    assert audit.action == "create_source"


def test_create_source_duplicate_name_conflict(db_session: Session, evidence_store: EvidenceStore):
    service = IngestionService(evidence_store=evidence_store)
    service.create_source(db=db_session, name="unique-router")

    # Lowercase or case variation should be rejected with 409
    with pytest.raises(APIError) as exc_info:
        service.create_source(db=db_session, name="UNIQUE-ROUTER")
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "SOURCE_NAME_CONFLICT"


def test_create_ingestion_job_success(db_session: Session, evidence_store: EvidenceStore):
    service = IngestionService(evidence_store=evidence_store)
    source = service.create_source(db=db_session, name="source-for-job")

    log_data = b"CEF:0|AcmeNet|EdgeFirewall|4.2|ALLOW-001|Allowed|3|src=10.0.1.25\n"
    stream = io.BytesIO(log_data)

    job = service.create_ingestion_job(
        db=db_session,
        source_id=source.id,
        input_format="cef",
        original_filename="firewall_cef.log",
        file_stream=stream,
    )

    assert job.id is not None
    assert job.source_id == source.id
    assert job.input_format == "cef"
    assert job.status == "queued"
    assert job.raw_file_size == len(log_data)
    assert len(job.raw_file_sha256) == 64

    # Stored file should exist in evidence store
    stored_bytes = evidence_store.read(job.raw_file_path)
    assert stored_bytes == log_data


def test_create_ingestion_job_invalid_source(db_session: Session, evidence_store: EvidenceStore):
    service = IngestionService(evidence_store=evidence_store)
    non_existent_source_id = uuid.uuid4()
    stream = io.BytesIO(b"dummy")

    with pytest.raises(APIError) as exc_info:
        service.create_ingestion_job(
            db=db_session,
            source_id=non_existent_source_id,
            input_format="json",
            original_filename="test.json",
            file_stream=stream,
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "SOURCE_NOT_FOUND"


def test_create_ingestion_job_unsupported_format(
    db_session: Session, evidence_store: EvidenceStore
):
    service = IngestionService(evidence_store=evidence_store)
    source = service.create_source(db=db_session, name="source-for-bad-format")
    stream = io.BytesIO(b"dummy")

    with pytest.raises(APIError) as exc_info:
        service.create_ingestion_job(
            db=db_session,
            source_id=source.id,
            input_format="unsupported_xyz",
            original_filename="test.log",
            file_stream=stream,
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "UNSUPPORTED_FORMAT"
