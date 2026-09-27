import base64
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ulpf.api.errors import APIError
from ulpf.db import get_db
from ulpf.models.normalized_event import NormalizedEvent
from ulpf.models.raw_event import RawEvent

router = APIRouter(tags=["Events & Evidence"])


class NormalizedEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    raw_event_id: uuid.UUID
    source_id: uuid.UUID
    ocsf_version: str
    class_uid: int | None
    event_time: datetime | None
    event_data: dict[str, Any]


class EventListResponse(BaseModel):
    items: list[NormalizedEventResponse]
    next_cursor: str | None


class RawEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    source_id: uuid.UUID
    record_index: int
    raw_sha256: str
    raw_text: str | None
    received_at: datetime


class VerifyHashResponse(BaseModel):
    raw_event_id: uuid.UUID
    stored_sha256: str
    computed_sha256: str
    matches: bool
    verified_at: datetime


def encode_cursor(event_time: datetime | None, event_id: uuid.UUID) -> str:
    ts_str = event_time.isoformat() if event_time else ""
    raw = f"{ts_str}|{event_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def decode_cursor(cursor_str: str) -> tuple[datetime | None, uuid.UUID]:
    try:
        decoded = base64.urlsafe_b64decode(cursor_str.encode("utf-8")).decode("utf-8")
        parts = decoded.split("|")
        ts = datetime.fromisoformat(parts[0]) if parts[0] else None
        event_id = uuid.UUID(parts[1])
        return ts, event_id
    except Exception as err:
        raise APIError(
            code="INVALID_CURSOR",
            message="Invalid pagination cursor format",
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from err


@router.get("/events", response_model=EventListResponse)
def search_events(
    source_id: uuid.UUID | None = Query(None, description="Filter by source ID"),
    class_uid: int | None = Query(None, description="Filter by OCSF class UID"),
    from_time: datetime | None = Query(None, alias="from", description="Filter from ISO time"),
    to_time: datetime | None = Query(None, alias="to", description="Filter to ISO time"),
    limit: int = Query(50, ge=1, le=200, description="Items per page (max 200)"),
    cursor: str | None = Query(None, description="Cursor for next page"),
    db: Session = Depends(get_db),
) -> EventListResponse:
    stmt = select(NormalizedEvent)

    if source_id:
        stmt = stmt.where(NormalizedEvent.source_id == source_id)
    if class_uid:
        stmt = stmt.where(NormalizedEvent.class_uid == class_uid)
    if from_time:
        stmt = stmt.where(NormalizedEvent.event_time >= from_time)
    if to_time:
        stmt = stmt.where(NormalizedEvent.event_time <= to_time)

    # Order by event_time DESC, id DESC
    stmt = stmt.order_by(desc(NormalizedEvent.event_time), desc(NormalizedEvent.id))

    if cursor:
        cursor_time, cursor_id = decode_cursor(cursor)
        if cursor_time:
            stmt = stmt.where(
                (NormalizedEvent.event_time < cursor_time)
                | ((NormalizedEvent.event_time == cursor_time) & (NormalizedEvent.id < cursor_id))
            )
        else:
            stmt = stmt.where(NormalizedEvent.id < cursor_id)

    # Fetch limit + 1 to detect if there's a next page
    stmt = stmt.limit(limit + 1)
    results = list(db.execute(stmt).scalars().all())

    next_cursor = None
    if len(results) > limit:
        next_item = results[limit - 1]
        next_cursor = encode_cursor(next_item.event_time, next_item.id)
        results = results[:limit]

    return EventListResponse(
        items=[NormalizedEventResponse.model_validate(ev) for ev in results],
        next_cursor=next_cursor,
    )


@router.get("/events/{event_id}", response_model=NormalizedEventResponse)
def get_event(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> NormalizedEventResponse:
    ev = db.get(NormalizedEvent, event_id)
    if not ev:
        raise APIError(
            code="EVENT_NOT_FOUND",
            message=f"Normalized event '{event_id}' does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return NormalizedEventResponse.model_validate(ev)


@router.get("/raw-events/{raw_event_id}", response_model=RawEventResponse)
def get_raw_event(
    raw_event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> RawEventResponse:
    raw_ev = db.get(RawEvent, raw_event_id)
    if not raw_ev:
        raise APIError(
            code="RAW_EVENT_NOT_FOUND",
            message=f"Raw evidence '{raw_event_id}' does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return RawEventResponse.model_validate(raw_ev)


@router.post("/raw-events/{raw_event_id}/verify", response_model=VerifyHashResponse)
def verify_raw_event_hash(
    raw_event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> VerifyHashResponse:
    import hashlib
    import hmac

    raw_ev = db.get(RawEvent, raw_event_id)
    if not raw_ev:
        raise APIError(
            code="RAW_EVENT_NOT_FOUND",
            message=f"Raw evidence '{raw_event_id}' does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    computed = hashlib.sha256(raw_ev.raw_bytes).hexdigest()
    matches = hmac.compare_digest(computed.lower(), raw_ev.raw_sha256.lower())

    return VerifyHashResponse(
        raw_event_id=raw_ev.id,
        stored_sha256=raw_ev.raw_sha256,
        computed_sha256=computed,
        matches=matches,
        verified_at=datetime.now(UTC),
    )


@router.get("/exports/events")
def export_events(
    source_id: uuid.UUID | None = Query(None),
    format: str = Query("jsonl"),
    from_time: datetime | None = Query(None, alias="from"),
    to_time: datetime | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    if format.lower() != "jsonl":
        raise APIError(
            code="UNSUPPORTED_EXPORT_FORMAT",
            message="Only 'jsonl' format is currently supported for streaming export",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    stmt = select(NormalizedEvent).order_by(desc(NormalizedEvent.event_time))
    if source_id:
        stmt = stmt.where(NormalizedEvent.source_id == source_id)
    if from_time:
        stmt = stmt.where(NormalizedEvent.event_time >= from_time)
    if to_time:
        stmt = stmt.where(NormalizedEvent.event_time <= to_time)

    def event_stream():
        results = db.execute(stmt).scalars()
        for ev in results:
            line = json.dumps(ev.event_data) + "\n"
            yield line.encode("utf-8")

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="export_events.jsonl"'},
    )
