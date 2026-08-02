# app/api/cctv.py
# CCTV endpoints: MJPEG live stream, status, events, and enable/disable.

import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import require_role
from app.core.security import decode_access_token
from app.models.db_models import User
from app.services.cctv_service import cctv_service

router = APIRouter(prefix="/cctv", tags=["CCTV"])


class CctvSettings(BaseModel):
    detect: bool | None = None
    recognize: bool | None = None
    auto_capture: bool | None = None
    capture_min: float | None = None
    capture_max: float | None = None


def _authorize_stream(token: str | None):
    """<img> tags can't send Authorization headers, so the MJPEG stream
    accepts the JWT as a query param instead."""
    if not token:
        raise HTTPException(status_code=401, detail="Token required as ?token= query param.")
    if decode_access_token(token) is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")


@router.get("/stream")
def stream(token: str | None = None):
    _authorize_stream(token)
    if not cctv_service.is_running():
        raise HTTPException(status_code=503, detail="CCTV service is not running.")

    def generate():
        while True:
            jpeg = cctv_service.get_latest_jpeg()
            if jpeg is not None:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
            time.sleep(0.05)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/status")
def status(_: None = Depends(require_role("teacher", "admin"))):
    return cctv_service.get_status()


@router.get("/events")
def events(limit: int = 50, _: None = Depends(require_role("teacher", "admin"))):
    return {"events": cctv_service.get_events(limit)}


@router.post("/toggle")
def toggle(_: None = Depends(require_role("admin"))):
    running = cctv_service.toggle()
    return {"running": running}


@router.post("/settings")
def update_settings(
    payload: CctvSettings,
    current_user: User = Depends(require_role("teacher", "admin")),
):
    if current_user.role != "admin":
        if (payload.auto_capture is not None or payload.capture_min is not None
                or payload.capture_max is not None):
            raise HTTPException(
                status_code=403,
                detail="Auto-capture and interval settings require an admin.",
            )
    try:
        return cctv_service.update_settings(
            detect=payload.detect,
            recognize=payload.recognize,
            auto_capture=payload.auto_capture,
            capture_min=payload.capture_min,
            capture_max=payload.capture_max,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
