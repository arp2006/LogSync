import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ulpf.config import settings
from ulpf.models.job import IngestionJob
from ulpf.models.normalized_event import NormalizedEvent
from ulpf.models.parser_error import ParserError
from ulpf.models.raw_event import RawEvent
from ulpf.parsers.base import ParseContext, ParseError
from ulpf.parsers.registry import ParserRegistry, default_registry
from ulpf.services.evidence_store import EvidenceStore
from ulpf.services.normalization import NormalizationError, OCSFNormalizer


class JobProcessor:
    def __init__(
        self,
        evidence_store: EvidenceStore | None = None,
        registry: ParserRegistry | None = None,
        normalizer: OCSFNormalizer | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.evidence_store = evidence_store or EvidenceStore(settings.raw_data_dir)
        self.registry = registry or default_registry
        self.normalizer = normalizer or OCSFNormalizer()
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"

    def claim_next_job(self, db: Session) -> IngestionJob | None:
        """
        Atomically claim a single queued job using FOR UPDATE SKIP LOCKED (PostgreSQL)
        or fallback for SQLite.
        """
        dialect = db.bind.dialect.name if db.bind else "postgresql"
        if dialect == "postgresql":
            claim_sql = text(
                """
                WITH next_job AS (
                    SELECT id
                    FROM ingestion_jobs
                    WHERE status = 'queued'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE ingestion_jobs
                SET status = 'processing',
                    worker_id = :worker_id,
                    started_at = now(),
                    attempt_count = attempt_count + 1
                WHERE id = (SELECT id FROM next_job)
                RETURNING id;
                """
            )
            result = db.execute(claim_sql, {"worker_id": self.worker_id}).fetchone()
            db.commit()
            if not result:
                return None
            return db.get(IngestionJob, result[0])
        else:
            # Fallback for SQLite in test environments
            stmt = (
                select(IngestionJob)
                .where(IngestionJob.status == "queued")
                .order_by(IngestionJob.created_at)
                .limit(1)
            )
            job = db.execute(stmt).scalar_one_or_none()
            if not job:
                return None
            job.status = "processing"
            job.worker_id = self.worker_id
            job.started_at = datetime.now(UTC)
            job.attempt_count += 1
            db.commit()
            db.refresh(job)
            return job

    def _split_records(self, raw_bytes: bytes) -> list[bytes]:
        """
        Split raw evidence file into discrete record byte lines.
        Omits empty lines.
        """
        lines = raw_bytes.splitlines()
        return [line for line in lines if line.strip()]

    def process_job(self, db: Session, job_id: uuid.UUID | str) -> IngestionJob:
        """
        Execute full pipeline on claimed job:
        1. Read raw evidence
        2. Split records
        3. Insert raw_events
        4. Parse -> Normalize -> Validate
        5. Persist normalized_events or parser_errors
        6. Update job status
        """
        resolved_id = uuid.UUID(str(job_id))
        job = db.get(IngestionJob, resolved_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        source = job.source
        parser = self.registry.get(job.input_format)

        try:
            raw_content = self.evidence_store.read(job.raw_file_path)
        except Exception as err:
            job.status = "failed"
            job.finished_at = datetime.now(UTC)
            job.error_summary = f"Failed to read raw evidence: {err}"
            db.commit()
            return job

        record_lines = self._split_records(raw_content)
        total_records = len(record_lines)
        processed_records = 0
        failed_records = 0

        # Process records in batches
        batch_size = 50
        for batch_start in range(0, total_records, batch_size):
            batch = record_lines[batch_start : batch_start + batch_size]
            for idx_in_batch, raw_line in enumerate(batch):
                record_index = batch_start + idx_in_batch
                line_sha256 = hashlib.sha256(raw_line).hexdigest()

                raw_text_repr: str | None = None
                try:
                    raw_text_repr = raw_line.decode("utf-8")
                except UnicodeDecodeError:
                    raw_text_repr = None

                raw_event_id = uuid.uuid4()
                raw_event = RawEvent(
                    id=raw_event_id,
                    job_id=job.id,
                    source_id=source.id,
                    record_index=record_index,
                    raw_bytes=raw_line,
                    raw_text=raw_text_repr,
                    raw_sha256=line_sha256,
                    received_at=job.created_at,
                )
                db.add(raw_event)
                db.flush()

                # Parse record
                context = ParseContext(
                    source_id=str(source.id),
                    job_id=str(job.id),
                    record_index=record_index,
                    received_at=job.created_at,
                )

                try:
                    parse_result = parser.parse(raw_line, context)
                except ParseError as parse_err:
                    error_rec = ParserError(
                        raw_event_id=raw_event.id,
                        parser_name=parser.name,
                        parser_version=parser.version,
                        stage="parse",
                        error_code=parse_err.error_code,
                        message=parse_err.message,
                        details=parse_err.details,
                    )
                    db.add(error_rec)
                    failed_records += 1
                    continue
                except Exception as unk_err:
                    error_rec = ParserError(
                        raw_event_id=raw_event.id,
                        parser_name=parser.name,
                        parser_version=parser.version,
                        stage="parse",
                        error_code="UNEXPECTED_PARSE_ERROR",
                        message=str(unk_err),
                        details={},
                    )
                    db.add(error_rec)
                    failed_records += 1
                    continue

                # Normalize & Validate
                try:
                    norm_result = self.normalizer.normalize(
                        parsed=parse_result.event,
                        source=source,
                        raw_event_id=str(raw_event.id),
                        raw_sha256=line_sha256,
                        storage_ref=job.raw_file_path,
                        parser_name=parse_result.parser_name,
                        parser_version=parse_result.parser_version,
                        received_at=job.created_at,
                    )

                    norm_event = NormalizedEvent(
                        raw_event_id=raw_event.id,
                        source_id=source.id,
                        job_id=job.id,
                        ocsf_version=norm_result.ocsf_version,
                        class_uid=norm_result.class_uid,
                        category_uid=norm_result.category_uid,
                        activity_id=norm_result.activity_id,
                        event_time=norm_result.event_time,
                        severity_id=norm_result.severity_id,
                        event_data=norm_result.event_data,
                    )
                    db.add(norm_event)
                    processed_records += 1

                except NormalizationError as norm_err:
                    is_endpoint_error = "IP" in norm_err.error_code or "PORT" in norm_err.error_code
                    stage_name = "normalize" if is_endpoint_error else "validate"
                    error_rec = ParserError(
                        raw_event_id=raw_event.id,
                        parser_name=parser.name,
                        parser_version=parser.version,
                        stage=stage_name,
                        error_code=norm_err.error_code,
                        message=norm_err.message,
                        details={},
                    )
                    db.add(error_rec)
                    failed_records += 1

            # Commit batch
            db.commit()

        # Finalize job outcome
        job.total_records = total_records
        job.processed_records = processed_records
        job.failed_records = failed_records
        job.finished_at = datetime.now(UTC)

        if failed_records == 0:
            job.status = "completed"
            job.error_summary = None
        elif processed_records > 0:
            job.status = "completed_with_errors"
            job.error_summary = f"{failed_records} records failed parsing or validation"
        else:
            job.status = "failed"
            job.error_summary = f"All {failed_records} records failed parsing or validation"

        db.commit()
        db.refresh(job)
        return job

    def claim_and_process_next(self, db: Session) -> IngestionJob | None:
        """Helper to claim and immediately process the next available queued job."""
        job = self.claim_next_job(db)
        if not job:
            return None
        return self.process_job(db, job.id)
