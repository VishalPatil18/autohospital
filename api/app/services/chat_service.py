from __future__ import annotations

from typing import AsyncIterator
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import AnthropicClient
from app.ai.retrieval import retrieve
from app.db.models import ChatMessage


async def run_patient_chat(
    session: AsyncSession,
    user_id: UUID,
    message: str,
    conversation_id: UUID | None = None,
) -> tuple[AsyncIterator[str], UUID, UUID]:
    """
    Run a chat conversation for a patient.

    Retrieves relevant document chunks, streams Claude responses, and persists messages.

    Args:
        session: Database session
        user_id: Patient's user ID
        message: User's message
        conversation_id: Existing conversation ID, or None for new

    Returns:
        (token_stream, conversation_id, message_id)
        - token_stream: AsyncIterator of response tokens
        - conversation_id: UUID of the conversation
        - message_id: UUID of the user's message in the database
    """
    import uuid as uuid_module

    # Use or generate conversation ID
    if not conversation_id:
        conversation_id = uuid_module.uuid4()

    # Retrieve relevant document chunks for this patient
    chunks_list = await retrieve(message, [user_id], k=8)
    chunk_texts = [chunk.text for chunk in chunks_list]

    # Load conversation history
    history_result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.asc())
    )
    history_messages = history_result.scalars().all()

    # Build messages list for Claude
    messages = []
    for hm in history_messages:
        messages.append(
            {
                "role": hm.role,
                "content": hm.content,
            }
        )

    # Add current user message
    messages.append({"role": "user", "content": message})

    # Persist user message
    user_message_id = uuid_module.uuid4()
    user_msg_obj = ChatMessage(
        id=user_message_id,
        user_id=user_id,
        conversation_id=conversation_id,
        role="user",
        content=message,
    )
    session.add(user_msg_obj)
    await session.flush()

    # Create assistant message for streaming
    assistant_message_id = uuid_module.uuid4()
    assistant_msg_obj = ChatMessage(
        id=assistant_message_id,
        user_id=user_id,
        conversation_id=conversation_id,
        role="assistant",
        content="",  # Will be filled as tokens stream in
    )
    session.add(assistant_msg_obj)
    await session.flush()

    # Stream tokens from Claude
    client = AnthropicClient()
    token_stream = client.chat(messages, chunk_texts, scope="patient")

    return token_stream, conversation_id, user_message_id


async def stream_and_persist_chat(
    session: AsyncSession,
    user_id: UUID,
    token_stream: AsyncIterator[str],
    assistant_message_id: UUID,
) -> AsyncIterator[str]:
    """
    Consume token stream and persist the full response.

    Args:
        session: Database session
        user_id: Patient's user ID (for re-loading the message)
        token_stream: Token stream from Claude
        assistant_message_id: UUID of the assistant message to update

    Yields:
        Tokens as they arrive
    """
    full_response = ""

    async for token in token_stream:
        full_response += token
        yield token

    # Update assistant message with full response
    result = await session.execute(
        select(ChatMessage).where(ChatMessage.id == assistant_message_id)
    )
    assistant_msg = result.scalars().first()
    if assistant_msg:
        assistant_msg.content = full_response
        session.add(assistant_msg)
        await session.commit()
