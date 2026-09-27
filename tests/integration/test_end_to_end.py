import io
import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ulpf.services.evidence_store import EvidenceStore
from ulpf.worker.processor import JobProcessor


def test_complete_end_to_end_telemetry_pipeline(
    client: TestClient, db_session: Session, evidence_store: EvidenceStore
):
    # 1. Register Edge Firewall Source
    source_resp = client.post(
        "/api/v1/sources",
        json={
            "name": "edge-fw-primary",
            "source_type": "firewall",
            "vendor": "AcmeNet",
            "product": "EdgeFirewall",
        },
    )
    assert source_resp.status_code == 201
    source_id = source_resp.json()["id"]

    # 2. Prepare multi-record CEF file with valid and malformed records
    cef_records = (
        # Valid 1: Allow TCP connection
        b"CEF:0|AcmeNet|EdgeFirewall|4.2|ALLOW-001|Connection allowed|3|"
        b"src=10.0.1.25 spt=51514 dst=192.0.2.20 dpt=443 proto=TCP act=allow\n"
        # Valid 2: Deny UDP connection
        b"CEF:0|AcmeNet|EdgeFirewall|4.2|DENY-002|Connection dropped|7|"
        b"src=198.51.100.5 spt=12345 dst=192.0.2.50 dpt=53 proto=UDP act=drop\n"
        # Malformed 1: Invalid header (fewer than 7 fields)
        b"CEF:0|Truncated|Header\n"
        # Malformed 2: Invalid IP address
        b"CEF:0|AcmeNet|EdgeFirewall|4.2|BAD-003|Bad IP|5|"
        b"src=999.999.999.999 spt=80 dst=192.0.2.20 dpt=80 act=deny\n"
    )

    # 3. Upload File to Ingestion API
    upload_resp = client.post(
        "/api/v1/ingestion-jobs",
        data={"source_id": source_id, "format": "cef"},
        files={"file": ("perimeter_firewall.log", io.BytesIO(cef_records), "text/plain")},
    )
    assert upload_resp.status_code == 202
    job_id = upload_resp.json()["job_id"]

    # 4. Trigger Worker Processing
    processor = JobProcessor(evidence_store=evidence_store)
    processed_job = processor.process_job(db=db_session, job_id=job_id)

    assert processed_job.status == "completed_with_errors"
    assert processed_job.total_records == 4
    assert processed_job.processed_records == 2
    assert processed_job.failed_records == 2

    # 5. Query Ingestion Job Status via API
    job_status_resp = client.get(f"/api/v1/ingestion-jobs/{job_id}")
    assert job_status_resp.status_code == 200
    job_data = job_status_resp.json()
    assert job_data["status"] == "completed_with_errors"
    assert job_data["total_records"] == 4
    assert job_data["processed_records"] == 2
    assert job_data["failed_records"] == 2

    # 6. Query Job Errors via API
    errors_resp = client.get(f"/api/v1/ingestion-jobs/{job_id}/errors")
    assert errors_resp.status_code == 200
    errors_data = errors_resp.json()["items"]
    assert len(errors_data) == 2
    error_codes = {e["error_code"] for e in errors_data}
    assert "CEF_INVALID_HEADER" in error_codes
    assert "INVALID_IP_ADDRESS" in error_codes

    # 7. Search Normalized Events via API
    events_resp = client.get(f"/api/v1/events?source_id={source_id}&class_uid=4001")
    assert events_resp.status_code == 200
    events_data = events_resp.json()["items"]
    assert len(events_data) == 2

    # Inspect first normalized event
    ev1 = events_data[0]
    assert ev1["class_uid"] == 4001
    assert ev1["ocsf_version"] == "1.1.0"
    raw_event_id = ev1["raw_event_id"]

    # 8. Check Forensic Traceability: Retrieve Exact Raw Evidence
    raw_resp = client.get(f"/api/v1/raw-events/{raw_event_id}")
    assert raw_resp.status_code == 200
    raw_data = raw_resp.json()
    assert raw_data["id"] == raw_event_id
    assert raw_data["job_id"] == job_id
    assert "CEF:0|AcmeNet|EdgeFirewall" in raw_data["raw_text"]

    # 9. Verify Raw Evidence SHA-256 Digest
    verify_resp = client.post(f"/api/v1/raw-events/{raw_event_id}/verify")
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["matches"] is True
    assert verify_data["stored_sha256"] == verify_data["computed_sha256"]

    # 10. Streaming Export Normalized Events (JSONL)
    export_resp = client.get(f"/api/v1/exports/events?source_id={source_id}&format=jsonl")
    assert export_resp.status_code == 200
    lines = export_resp.text.strip().split("\n")
    assert len(lines) == 2
    for line in lines:
        parsed_json = json.loads(line)
        assert parsed_json["schema"]["name"] == "OCSF"
        assert parsed_json["ocsf"]["class_uid"] == 4001


def test_syslog_and_json_ingestion_end_to_end(
    client: TestClient, db_session: Session, evidence_store: EvidenceStore
):
    # Register Syslog router
    source_resp = client.post(
        "/api/v1/sources",
        json={"name": "edge-router-01", "source_type": "router", "vendor": "AcmeNet"},
    )
    source_id = source_resp.json()["id"]

    syslog_data = (
        b"<134>1 2026-09-27T12:30:15Z edge-router-01 routerd 712 - - "
        b"Denied TCP connection from 10.0.1.25:51514 to 192.0.2.20:443\n"
    )

    upload_resp = client.post(
        "/api/v1/ingestion-jobs",
        data={"source_id": source_id, "format": "syslog"},
        files={"file": ("syslog.log", io.BytesIO(syslog_data), "text/plain")},
    )
    job_id = upload_resp.json()["job_id"]

    processor = JobProcessor(evidence_store=evidence_store)
    job = processor.process_job(db=db_session, job_id=job_id)
    assert job.status == "completed"
    assert job.total_records == 1
    assert job.processed_records == 1
    assert job.failed_records == 0

    events = client.get(f"/api/v1/events?source_id={source_id}").json()["items"]
    assert len(events) == 1
    assert events[0]["class_uid"] == 4001
    assert events[0]["event_data"]["ocsf"]["src_endpoint"]["ip"] == "10.0.1.25"
    assert events[0]["event_data"]["ocsf"]["dst_endpoint"]["ip"] == "192.0.2.20"
