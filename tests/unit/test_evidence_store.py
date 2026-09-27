import hashlib
import io
import uuid

import pytest

from ulpf.services.evidence_store import (
    EvidenceStore,
    EvidenceStoreError,
    PathTraversalError,
)


def test_evidence_store_save_and_read(evidence_store: EvidenceStore):
    job_id = str(uuid.uuid4())
    test_content = b"CEF:0|AcmeNet|EdgeFirewall|4.2|ALLOW-001|Connection allowed|3|src=10.0.1.25\n"
    expected_sha256 = hashlib.sha256(test_content).hexdigest()

    stored = evidence_store.save_upload(job_id=job_id, stream_or_chunks=test_content)

    assert stored.path.exists()
    assert stored.path.name == "original.bin"
    assert stored.sha256 == expected_sha256
    assert stored.size_bytes == len(test_content)

    # Read back
    read_bytes = evidence_store.read(stored.relative_path)
    assert read_bytes == test_content


def test_evidence_store_streaming(evidence_store: EvidenceStore):
    job_id = str(uuid.uuid4())
    chunks = [b"chunk_1_", b"chunk_2_", b"chunk_3"]
    full_content = b"".join(chunks)
    expected_sha256 = hashlib.sha256(full_content).hexdigest()

    stream = io.BytesIO(full_content)
    stored = evidence_store.save_upload(job_id=job_id, stream_or_chunks=stream)

    assert stored.size_bytes == len(full_content)
    assert stored.sha256 == expected_sha256
    assert evidence_store.read(stored.relative_path) == full_content


def test_evidence_store_hash_verification(evidence_store: EvidenceStore):
    job_id = str(uuid.uuid4())
    test_content = b"test syslog payload <134>1 2026-09-27T12:30:15Z edge-router-01"
    correct_hash = hashlib.sha256(test_content).hexdigest()
    tampered_hash = "0" * 64

    stored = evidence_store.save_upload(job_id=job_id, stream_or_chunks=test_content)

    # Correct hash matches
    assert evidence_store.verify(stored.relative_path, correct_hash) is True
    # Tampered hash does not match
    assert evidence_store.verify(stored.relative_path, tampered_hash) is False


def test_evidence_store_path_traversal_protection(evidence_store: EvidenceStore):
    # Attempting to read outside base_dir must raise PathTraversalError
    with pytest.raises(PathTraversalError):
        evidence_store.read("../../etc/passwd")

    with pytest.raises(PathTraversalError):
        evidence_store.verify("../../../secret.key", "somehash")


def test_evidence_store_file_size_limit(evidence_store: EvidenceStore):
    job_id = str(uuid.uuid4())
    large_content = b"A" * 1024  # 1 KB

    # Set limit to 500 bytes
    with pytest.raises(EvidenceStoreError, match="File size exceeds maximum"):
        evidence_store.save_upload(
            job_id=job_id,
            stream_or_chunks=large_content,
            max_size_bytes=500,
        )

    # Check that temporary files were cleaned up
    job_dir = evidence_store._get_target_dir(job_id)
    assert not job_dir.exists() or len(list(job_dir.glob("*.tmp"))) == 0
