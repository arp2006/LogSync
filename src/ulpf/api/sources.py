import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ulpf.api.errors import APIError
from ulpf.db import get_db
from ulpf.services.ingestion_service import IngestionService

router = APIRouter(prefix="/sources", tags=["Sources"])


class SourceCreateRequest(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=255, description="Unique source identifier/name"
    )
    source_type: str = Field(default="network_device", description="Device or log source type")
    vendor: str | None = Field(default=None, description="Device vendor (e.g. AcmeNet, Cisco)")
    product: str | None = Field(default=None, description="Product name (e.g. EdgeFirewall)")
    description: str | None = Field(default=None, description="Human readable description")
    config: dict[str, Any] = Field(default_factory=dict, description="Custom source configuration")


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    source_type: str
    vendor: str | None = None
    product: str | None = None
    is_active: bool
    created_at: datetime


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: SourceCreateRequest,
    db: Session = Depends(get_db),
) -> SourceResponse:
    service = IngestionService()
    source = service.create_source(
        db=db,
        name=payload.name,
        source_type=payload.source_type,
        vendor=payload.vendor,
        product=payload.product,
        description=payload.description,
        config=payload.config,
    )
    return SourceResponse.model_validate(source)


@router.get("", response_model=list[SourceResponse])
def list_sources(
    active_only: bool = False,
    db: Session = Depends(get_db),
) -> list[SourceResponse]:
    service = IngestionService()
    sources = service.list_sources(db=db, active_only=active_only)
    return [SourceResponse.model_validate(s) for s in sources]


@router.get("/{source_id}", response_model=SourceResponse)
def get_source(
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> SourceResponse:
    service = IngestionService()
    source = service.get_source(db=db, source_id=source_id)
    if not source:
        raise APIError(
            code="SOURCE_NOT_FOUND",
            message=f"Source with id '{source_id}' does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return SourceResponse.model_validate(source)
