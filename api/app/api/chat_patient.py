from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.schemas import ChatRequest
from app.db.session import get_db
from app.services import chat_service

router = APIRouter(tags=["chat"])


@router.post("/chat/patient")
async def chat_patient(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Patient chat endpoint with Server-Sent Events (SSE) streaming.

    Request body:
    - message: str — The user's message
    - conversation_id: str | None — Optional existing conversation ID

    Response: EventSource stream with tokens
    - Each token is sent as JSON: {"token": "..."}
    - On error, sends: {"error": "..."}
    """
    try:
        # Convert conversation_id string to UUID if provided
        conversation_id = None
        if request.conversation_id:
            try:
                conversation_id = UUID(request.conversation_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid conversation_id format")

        # Run chat and get token stream
        token_stream, conv_id, msg_id = await chat_service.run_patient_chat(
            session,
            current_user["id"],
            request.message,
            conversation_id,
        )

        # Stream tokens as SSE
        async def event_generator():
            try:
                # Send conversation ID to client
                yield f"data: {json.dumps({'type': 'conversation_id', 'value': str(conv_id)})}\n\n"

                # Stream tokens
                full_response = ""
                async for token in token_stream:
                    full_response += token
                    yield f"data: {json.dumps({'type': 'token', 'value': token})}\n\n"

                # Send completion
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

            except Exception as err:
                yield f"data: {json.dumps({'type': 'error', 'value': str(err)})}\n\n"
            finally:
                # Ensure final commit
                await session.commit()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as err:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {str(err)}",
        )
