import io
import uuid

from fastapi.testclient import TestClient


def test_health_endpoints(client: TestClient):
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "live"}

    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "database": "connected"}


def test_source_api_lifecycle(client: TestClient):
    # 1. Register Source
    payload = {
        "name": "edge-firewall-01",
        "source_type": "network_device",
        "vendor": "AcmeNet",
        "product": "EdgeFirewall",
        "description": "Firewall at the primary gateway",
        "config": {"timezone": "UTC"},
    }
    resp = client.post("/api/v1/sources", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "edge-firewall-01"
    assert data["vendor"] == "AcmeNet"
    assert data["is_active"] is True
    source_id = data["id"]

    # 2. Duplicate registration returns 409
    dup_resp = client.post("/api/v1/sources", json=payload)
    assert dup_resp.status_code == 409
    dup_data = dup_resp.json()
    assert dup_data["error"]["code"] == "SOURCE_NAME_CONFLICT"

    # 3. Retrieve source by ID
    get_resp = client.get(f"/api/v1/sources/{source_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == source_id

    # 4. List sources
    list_resp = client.get("/api/v1/sources")
    assert list_resp.status_code == 200
    sources = list_resp.json()
    assert len(sources) >= 1
    assert any(s["id"] == source_id for s in sources)


def test_ingestion_jobs_api_lifecycle(client: TestClient):
    # Register source first
    source_resp = client.post(
        "/api/v1/sources",
        json={"name": "vpn-gateway-01", "source_type": "vpn", "vendor": "AcmeNet"},
    )
    assert source_resp.status_code == 201
    source_id = source_resp.json()["id"]

    # Upload valid file
    file_bytes = b'{"timestamp":"2026-09-27T12:31:00Z","user":"alice","action":"auth_fail"}\n'
    files = {"file": ("vpn_events.jsonl", io.BytesIO(file_bytes), "application/json")}
    data = {
        "source_id": source_id,
        "format": "json",
    }
    upload_resp = client.post("/api/v1/ingestion-jobs", data=data, files=files)
    assert upload_resp.status_code == 202
    job_info = upload_resp.json()
    assert job_info["status"] == "queued"
    assert job_info["format"] == "json"
    assert job_info["raw_file_size"] == len(file_bytes)
    assert len(job_info["raw_file_sha256"]) == 64
    job_id = job_info["job_id"]

    # Query job status
    job_resp = client.get(f"/api/v1/ingestion-jobs/{job_id}")
    assert job_resp.status_code == 200
    job_detail = job_resp.json()
    assert job_detail["job_id"] == job_id
    assert job_detail["status"] == "queued"
    assert job_detail["total_records"] == 0


def test_ingestion_jobs_invalid_format(client: TestClient):
    source_resp = client.post(
        "/api/v1/sources",
        json={"name": "test-device-invalid-fmt"},
    )
    source_id = source_resp.json()["id"]

    files = {"file": ("test.log", io.BytesIO(b"data"), "text/plain")}
    data = {"source_id": source_id, "format": "unsupported_fmt"}

    resp = client.post("/api/v1/ingestion-jobs", data=data, files=files)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "UNSUPPORTED_FORMAT"


def test_ingestion_jobs_invalid_source_id(client: TestClient):
    files = {"file": ("test.log", io.BytesIO(b"data"), "text/plain")}
    data = {"source_id": str(uuid.uuid4()), "format": "cef"}

    resp = client.post("/api/v1/ingestion-jobs", data=data, files=files)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "SOURCE_NOT_FOUND"


def test_ingestion_jobs_malformed_source_id(client: TestClient):
    files = {"file": ("test.log", io.BytesIO(b"data"), "text/plain")}
    data = {"source_id": "not-a-valid-uuid", "format": "cef"}

    resp = client.post("/api/v1/ingestion-jobs", data=data, files=files)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SOURCE_ID"
