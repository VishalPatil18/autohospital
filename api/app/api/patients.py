from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import JSONResponse

from app.core.auth import get_current_user

router = APIRouter(prefix="/patients", tags=["patients"])

_NOT_IMPLEMENTED = JSONResponse(
    status_code=501,
    content={"error": {"code": "not_implemented", "message": "Coming in Phase 3"}},
)


@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED


@router.get("/me/documents")
async def get_my_documents(current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED


@router.post("/me/documents")
async def upload_document(file: UploadFile, current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED


@router.post("/me/documents/{document_id}/translate")
async def translate_document(document_id: UUID, current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED


@router.get("/me/appointments")
async def get_my_appointments(current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED


@router.get("/me/notes")
async def get_my_notes(current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED
