from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import AnthropicClient
from app.ai.retrieval import retrieve
from app.db.models import ChatMessage
from app.services.guardrails import sanitize_chunks, scope_header

_llm = AnthropicClient()


async def run_chat(
    user_id: UUID,
    role: str,
    message: str,
    patient_ids: list[UUID],
    conversation_id: UUID,
    db: AsyncSession,
) -> AsyncIterator[str]:
    """
    Shared RAG chat pipeline used by both patient and doctor chat endpoints.

    Steps:
    1. Persist the user message.
    2. Load prior conversation history.
    3. Retrieve relevant chunks via pgvector similarity search.
    4. Sanitize chunks to neutralize prompt injection.
    5. Prepend scope-restriction header as first context chunk.
    6. Stream tokens from Claude.
    7. Persist the assembled assistant reply.

    Yields:
        Individual text tokens for SSE streaming.
    """
    # 1. Persist user message immediately (before streaming)
    user_msg = ChatMessage(
        id=uuid.uuid4(),
        user_id=user_id,
        conversation_id=conversation_id,
        role="user",
        content=message,
    )
    db.add(user_msg)
    await db.commit()

    # 2. Load conversation history (all messages in this conversation, ordered)
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .where(ChatMessage.id != user_msg.id)
        .order_by(ChatMessage.created_at.asc())
    )
    history_rows = result.scalars().all()
    history = [{"role": row.role, "content": row.content} for row in history_rows]
    messages = history + [{"role": "user", "content": message}]

    # 3. Retrieve relevant chunks (returns [] if no chunks ingested yet)
    chunks = await retrieve(message, patient_ids)

    # 4. Sanitize retrieved chunks
    clean_texts = sanitize_chunks(chunks)

    # 5. Prepend scope-restriction header so it lands in the LLM's context block
    context_with_scope = [scope_header(role, patient_ids)] + clean_texts

    # 6. Stream from Claude, collecting tokens for persistence
    collected: list[str] = []
    async for token in _llm.chat(messages, context_with_scope, scope=role):
        collected.append(token)
        yield token

    # 7. Persist assembled assistant reply
    assistant_text = "".join(collected)
    assistant_msg = ChatMessage(
        id=uuid.uuid4(),
        user_id=user_id,
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_text,
    )
    db.add(assistant_msg)
    await db.commit()
