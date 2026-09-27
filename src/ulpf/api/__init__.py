from fastapi import APIRouter

from ulpf.api.ingestion import router as ingestion_router
from ulpf.api.sources import router as sources_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(sources_router)
api_v1_router.include_router(ingestion_router)

__all__ = ["api_v1_router"]
