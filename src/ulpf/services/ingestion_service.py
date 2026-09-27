import uuid
from typing import Any, BinaryIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ulpf.api.errors import APIError
from ulpf.config import settings
from ulpf.models.audit_event import AuditEvent
from ulpf.models.job import IngestionJob
from ulpf.models.source import Source
from ulpf.services.evidence_store import EvidenceStore, EvidenceStoreError

SUPPORTED_FORMATS = {"cef", "syslog", "json"}


class IngestionService:
    def __init__(self, evidence_store: EvidenceStore | None = None) -> None:
        self.evidence_store = evidence_store or EvidenceStore(settings.raw_data_dir)

    def create_source(
        self,
        db: Session,
        name: str,
        source_type: str = "network_device",
        vendor: str | None = None,
        product: str | None = None,
        description: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> Source:
        # Check duplicate name case-insensitively
        stmt = select(Source).where(func.lower(Source.name) == name.strip().lower())
        existing = db.execute(stmt).scalar_one_or_none()
        if existing:
            raise APIError(
                code="SOURCE_NAME_CONFLICT",
                message=f"A source with name '{name}' already exists",
                status_code=409,
            )

        source = Source(
            name=name.strip(),
            source_type=source_type,
            vendor=vendor,
            product=product,
            description=description,
            config=config or {},
            is_active=True,
        )
        db.add(source)
        db.flush()

        # Audit record
        audit = AuditEvent(
            actor="system/api",
            action="create_source",
            resource_type="source",
            resource_id=source.id,
            details={"name": source.name, "vendor": source.vendor, "product": source.product},
        )
        db.add(audit)
        db.commit()
        db.refresh(source)
        return source

    def list_sources(self, db: Session, active_only: bool = False) -> list[Source]:
        stmt = select(Source).order_by(Source.created_at.desc())
        if active_only:
            stmt = stmt.where(Source.is_active.is_(True))
        return list(db.execute(stmt).scalars().all())

    def get_source(self, db: Session, source_id: uuid.UUID) -> Source | None:
        return db.get(Source, source_id)

    def create_ingestion_job(
        self,
        db: Session,
        source_id: uuid.UUID,
        input_format: str,
        original_filename: str,
        file_stream: BinaryIO,
    ) -> IngestionJob:
        normalized_format = input_format.strip().lower()
        if normalized_format not in SUPPORTED_FORMATS:
            formats_str = ", ".join(sorted(SUPPORTED_FORMATS))
            raise APIError(
                code="UNSUPPORTED_FORMAT",
                message=f"Unsupported format '{input_format}'. Supported formats: {formats_str}",
                status_code=400,
            )

        source = self.get_source(db, source_id)
        if not source or not source.is_active:
            raise APIError(
                code="SOURCE_NOT_FOUND",
                message="The requested source does not exist or is inactive",
                status_code=400,
            )

        job_id = uuid.uuid4()

        try:
            stored_evidence = self.evidence_store.save_upload(
                job_id=str(job_id),
                stream_or_chunks=file_stream,
                max_size_bytes=settings.max_upload_size_bytes,
            )
        except EvidenceStoreError as err:
            raise APIError(
                code="PAYLOAD_TOO_LARGE",
                message=str(err),
                status_code=413,
            ) from err
        except Exception as err:
            raise APIError(
                code="EVIDENCE_PERSISTENCE_FAILED",
                message=f"Failed to persist raw evidence: {err}",
                status_code=500,
            ) from err

        # Now persist ingestion job in database
        try:
            job = IngestionJob(
                id=job_id,
                source_id=source.id,
                original_filename=original_filename,
                input_format=normalized_format,
                status="queued",
                raw_file_path=stored_evidence.relative_path,
                raw_file_sha256=stored_evidence.sha256,
                raw_file_size=stored_evidence.size_bytes,
            )
            db.add(job)
            db.flush()

            audit = AuditEvent(
                actor="system/api",
                action="create_ingestion_job",
                resource_type="ingestion_job",
                resource_id=job.id,
                details={
                    "source_id": str(source.id),
                    "original_filename": original_filename,
                    "format": normalized_format,
                    "sha256": stored_evidence.sha256,
                    "size_bytes": stored_evidence.size_bytes,
                },
            )
            db.add(audit)
            db.commit()
            db.refresh(job)
            return job
        except Exception:
            db.rollback()
            # Clean up stored evidence if database transaction fails
            self.evidence_store.delete_job_evidence(str(job_id))
            raise

    def get_job(self, db: Session, job_id: uuid.UUID) -> IngestionJob | None:
        return db.get(IngestionJob, job_id)
