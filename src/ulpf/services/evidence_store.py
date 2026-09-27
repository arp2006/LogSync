import hashlib
import hmac
import os
import shutil
import tempfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO


@dataclass(frozen=True)
class StoredEvidence:
    path: Path
    relative_path: str
    sha256: str
    size_bytes: int


class EvidenceStoreError(Exception):
    """Base exception for evidence store errors."""


class PathTraversalError(EvidenceStoreError):
    """Raised when an invalid or escaping path is requested."""


class EvidenceStore:
    def __init__(self, base_dir: Path | str) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, relative_path: str | Path) -> Path:
        """
        Safely resolve a relative path under base_dir.
        Guarantees that the path cannot traverse outside base_dir.
        """
        # Strip any leading slashes to prevent root-relative path resolution
        cleaned_path = str(relative_path).lstrip("/\\")
        resolved = (self.base_dir / cleaned_path).resolve()
        try:
            resolved.relative_to(self.base_dir)
        except ValueError as err:
            raise PathTraversalError(f"Path traversal detected: {relative_path}") from err
        return resolved

    def _get_target_dir(self, job_id: str, timestamp: datetime | None = None) -> Path:
        """
        Generate structured directory: base_dir/YYYY/MM/<job-id>/
        """
        ts = timestamp or datetime.now(UTC)
        year_str = ts.strftime("%Y")
        month_str = ts.strftime("%m")
        return self.base_dir / year_str / month_str / str(job_id)

    def save_upload(
        self,
        job_id: str,
        stream_or_chunks: Iterable[bytes] | BinaryIO | bytes,
        timestamp: datetime | None = None,
        max_size_bytes: int | None = None,
    ) -> StoredEvidence:
        """
        Persist original bytes directly to a temporary file while computing SHA-256 and size.
        Atomically renames into final destination YYYY/MM/<job-id>/original.bin.
        Cleans up temporary files if interrupted or if size limit is exceeded.
        """
        target_dir = self._get_target_dir(job_id, timestamp)
        target_dir.mkdir(parents=True, exist_ok=True)
        final_path = target_dir / "original.bin"

        hasher = hashlib.sha256()
        total_size = 0

        # Create temporary file in the same directory/filesystem for atomic rename
        temp_fd, temp_file_path = tempfile.mkstemp(
            prefix="upload_",
            suffix=".tmp",
            dir=target_dir,
        )
        temp_path = Path(temp_file_path)

        try:
            with os.fdopen(temp_fd, "wb") as f:
                if isinstance(stream_or_chunks, bytes):
                    chunks: Iterator[bytes] = iter([stream_or_chunks])
                elif hasattr(stream_or_chunks, "read"):
                    def read_chunks() -> Iterator[bytes]:
                        while True:
                            chunk = stream_or_chunks.read(65536)  # 64 KB chunks
                            if not chunk:
                                break
                            yield chunk
                    chunks = read_chunks()
                else:
                    chunks = iter(stream_or_chunks)

                for chunk in chunks:
                    if not chunk:
                        continue
                    total_size += len(chunk)
                    if max_size_bytes is not None and total_size > max_size_bytes:
                        raise EvidenceStoreError(
                            f"File size exceeds maximum allowed limit of {max_size_bytes} bytes"
                        )
                    hasher.update(chunk)
                    f.write(chunk)
                f.flush()
                os.fsync(f.fileno())

            # Atomically rename into place
            temp_path.replace(final_path)

            relative_path = str(final_path.relative_to(self.base_dir))
            return StoredEvidence(
                path=final_path,
                relative_path=relative_path,
                sha256=hasher.hexdigest(),
                size_bytes=total_size,
            )
        except Exception:
            # Clean up temporary file on failure
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            # Clean up target dir if empty
            try:
                target_dir.rmdir()
            except OSError:
                pass
            raise

    def read(self, relative_path: str) -> bytes:
        """Read evidence using a validated path under the evidence root."""
        safe_path = self._resolve_safe_path(relative_path)
        if not safe_path.is_file():
            raise FileNotFoundError(f"Evidence file not found: {relative_path}")
        return safe_path.read_bytes()

    def verify(self, relative_path: str, expected_sha256: str) -> bool:
        """
        Recompute SHA-256 of stored evidence and compare using constant-time comparison.
        """
        safe_path = self._resolve_safe_path(relative_path)
        if not safe_path.is_file():
            raise FileNotFoundError(f"Evidence file not found: {relative_path}")

        hasher = hashlib.sha256()
        with safe_path.open("rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)

        computed = hasher.hexdigest()
        return hmac.compare_digest(computed.lower(), expected_sha256.lower())

    def delete_job_evidence(self, job_id: str, timestamp: datetime | None = None) -> bool:
        """Remove evidence directory for a job if needed (e.g. transactional rollback)."""
        target_dir = self._get_target_dir(job_id, timestamp)
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
            return True
        return False
