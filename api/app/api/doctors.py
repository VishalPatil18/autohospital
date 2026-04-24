from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.auth import get_current_user

router = APIRouter(tags=["doctors"])

_NOT_IMPLEMENTED = JSONResponse(
    status_code=501,
    content={"error": {"code": "not_implemented", "message": "Coming in Phase 3"}},
)


@router.get("/doctors/me/patients")
async def get_my_patients(current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED


@router.get("/patients/{patient_id}")
async def get_patient(patient_id: UUID, current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED


@router.post("/patients")
async def create_patient(current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED


@router.patch("/patients/{patient_id}")
async def update_patient(patient_id: UUID, current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED


@router.get("/appointments")
async def get_appointments(current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED


@router.post("/appointments")
async def create_appointment(current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED


@router.patch("/appointments/{appointment_id}")
async def update_appointment(appointment_id: UUID, current_user=Depends(get_current_user)):
    return _NOT_IMPLEMENTED
