from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket
from fastapi.responses import JSONResponse

from app.core.auth import get_current_user

router = APIRouter(tags=["scribe"])

_NOT_IMPLEMENTED = JSONResponse(
    status_code=501,
    content={"error": {"code": "not_implemented", "message": "Coming in Phase 3"}},
)


@router.websocket("/ws/scribe/{appointment_id}")
async def scribe_ws(appointment_id: UUID, websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.close(code=1001)


@router.post("/scribe/{appointment_id}/finalize")
async def finalize_scribe(appointment_id: UUID, current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED


@router.patch("/clinical-notes/{note_id}")
async def update_clinical_note(note_id: UUID, current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED


@router.post("/clinical-notes/{note_id}/sign")
async def sign_clinical_note(note_id: UUID, current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED
