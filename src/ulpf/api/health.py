from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ulpf.db import get_db

router = APIRouter(tags=["Health"])


@router.get("/health/live")
def health_live():
    return {"status": "live"}


@router.get("/health/ready")
def health_ready(response: Response, db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": "disconnected"}
