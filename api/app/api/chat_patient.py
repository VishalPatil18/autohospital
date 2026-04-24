from __future__ import annotations

import json
import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_role
from app.db.session import get_db
from app.services.chat_service import run_chat

router = APIRouter(tags=["chat"])


class PatientChatRequest(BaseModel):
    message: str
    conversation_id: UUID | None = None


@router.post("/chat/patient")
async def chat_patient(
    body: PatientChatRequest,
    current_user: Any = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    SSE endpoint for the patient chatbot.

    Retrieval is strictly scoped to the authenticated patient's own records.

    Streams tokens as:  data: {"token": "..."}\n\n
    Terminates with:    data: {"done": true}\n\n
    """
    patient_id: UUID = current_user.id
    conversation_id = body.conversation_id or uuid.uuid4()

    async def _event_stream():
        try:
            async for token in run_chat(
                user_id=patient_id,
                role="patient",
                message=body.message,
                patient_ids=[patient_id],
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
