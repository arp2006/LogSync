import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ulpf.api.errors import APIError
from ulpf.db import get_db
from ulpf.models.job import IngestionJob
from ulpf.services.ingestion_service import IngestionService

router = APIRouter(prefix="/ingestion-jobs", tags=["Ingestion"])


class JobCreateResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    format: str
    raw_file_sha256: str
    raw_file_size: int
    status_url: str


class JobDetailResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    format: str
    total_records: int
    processed_records: int
    failed_records: int
    attempt_count: int
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_summary: str | None = None


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_ingestion_job(
    file: UploadFile = File(..., description="Raw log file to ingest"),
    source_id: str = Form(..., description="UUID of the originating source device"),
    format: str = Form(..., description="Log format: cef, syslog, or json"),
    db: Session = Depends(get_db),
) -> JobCreateResponse:
    # Parse and validate UUID
    try:
        source_uuid = uuid.UUID(source_id)
    except ValueError as err:
        raise APIError(
            code="INVALID_SOURCE_ID",
            message=f"Invalid source_id format: '{source_id}'",
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from err

    service = IngestionService()
    filename = file.filename or "unknown_upload.bin"

    job = service.create_ingestion_job(
        db=db,
        source_id=source_uuid,
        input_format=format,
        original_filename=filename,
        file_stream=file.file,
    )

    return JobCreateResponse(
        job_id=job.id,
        status=job.status,
        format=job.input_format,
        raw_file_sha256=job.raw_file_sha256,
        raw_file_size=job.raw_file_size,
        status_url=f"/api/v1/ingestion-jobs/{job.id}",
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_ingestion_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> JobDetailResponse:
    service = IngestionService()
    job = service.get_job(db=db, job_id=job_id)
    if not job:
        raise APIError(
            code="JOB_NOT_FOUND",
            message=f"Ingestion job '{job_id}' does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return JobDetailResponse(
        job_id=job.id,
        status=job.status,
        format=job.input_format,
        total_records=job.total_records,
        processed_records=job.processed_records,
        failed_records=job.failed_records,
        attempt_count=job.attempt_count,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error_summary=job.error_summary,
    )


class JobErrorItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    raw_event_id: uuid.UUID
    parser_name: str
    parser_version: str
    stage: str
    error_code: str
    message: str


class JobErrorsResponse(BaseModel):
    items: list[JobErrorItem]
    next_cursor: str | None


@router.get("/{job_id}/errors", response_model=JobErrorsResponse)
def get_job_errors(
    job_id: uuid.UUID,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> JobErrorsResponse:
    from sqlalchemy import select

    from ulpf.models.parser_error import ParserError
    from ulpf.models.raw_event import RawEvent

    job = db.get(IngestionJob, job_id)
    if not job:
        raise APIError(
            code="JOB_NOT_FOUND",
            message=f"Ingestion job '{job_id}' does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    stmt = (
        select(ParserError)
        .join(RawEvent, ParserError.raw_event_id == RawEvent.id)
        .where(RawEvent.job_id == job_id)
        .order_by(ParserError.created_at.desc())
        .limit(limit)
    )
    errors = list(db.execute(stmt).scalars().all())

    return JobErrorsResponse(
        items=[JobErrorItem.model_validate(err) for err in errors],
        next_cursor=None,
    )
