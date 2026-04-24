from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.auth import get_current_user

router = APIRouter(tags=["chat"])

_NOT_IMPLEMENTED = JSONResponse(
    status_code=501,
    content={"error": {"code": "not_implemented", "message": "Coming in Phase 3"}},
)


@router.post("/chat/patient")
async def chat_patient(current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED
