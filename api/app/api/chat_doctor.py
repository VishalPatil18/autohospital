from __future__ import annotations

import json
import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_role
from app.db.models import CareTeam
from app.db.session import get_db
from app.services.chat_service import run_chat

router = APIRouter(tags=["chat"])


class DoctorChatRequest(BaseModel):
    message: str
    conversation_id: UUID | None = None
    patient_id: UUID | None = None


@router.post("/chat/doctor")
async def chat_doctor(
    body: DoctorChatRequest,
    current_user: Any = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    SSE endpoint for the doctor chatbot.

    Streams tokens as:  data: {"token": "..."}\n\n
    Terminates with:    data: {"done": true}\n\n

    Optional `patient_id` narrows retrieval to a single patient. If provided,
    it must belong to this doctor's care team — returns 403 otherwise.
    """
    doctor_id: UUID = current_user.id

    # Resolve all patient IDs in this doctor's care team
    result = await db.execute(
        select(CareTeam.patient_id).where(CareTeam.doctor_id == doctor_id)
    )
    care_team_patient_ids: list[UUID] = [row[0] for row in result.all()]

    if not care_team_patient_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No patients assigned to this doctor's care team.",
        )

    # If caller narrows to a specific patient, verify care-team membership
    if body.patient_id is not None:
        if body.patient_id not in care_team_patient_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Patient is not in your care team.",
            )
        patient_ids = [body.patient_id]
    else:
        patient_ids = care_team_patient_ids

    conversation_id = body.conversation_id or uuid.uuid4()

    async def _event_stream():
        try:
            async for token in run_chat(
                user_id=doctor_id,
                role="doctor",
                message=body.message,
                patient_ids=patient_ids,
                conversation_id=conversation_id,
                db=db,
            ):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception:
            yield f"data: {json.dumps({'error': 'stream_error'})}\n\n"
        finally:
            yield f"data: {json.dumps({'done': True, 'conversation_id': str(conversation_id)})}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
