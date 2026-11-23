"""Health and readiness check endpoints."""
import uuid
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import get_db

router = APIRouter(tags=["Health & Status"])


@router.get("/health", summary="Basic service health check")
def health_check(request: Request):
    req_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "service": "Fintech Sandbox API",
            "version": "0.1.0",
            "mode": "simulation",
        },
        "request_id": req_id,
    }


@router.get("/ready", summary="Readiness check for database connectivity")
def readiness_check(request: Request, db: Session = Depends(get_db)):
    req_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")
    try:
        db.execute(text("SELECT 1"))
        return {
            "success": True,
            "data": {
                "status": "ready",
                "database": "connected",
            },
            "request_id": req_id,
        }
    except Exception as e:
        return Response(
            content=f'{{"success": false, "error": {{"code": "DATABASE_UNAVAILABLE", "message": "{str(e)}"}}, "request_id": "{req_id}"}}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json",
        )
