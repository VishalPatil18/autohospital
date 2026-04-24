from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def with_user_context(session: AsyncSession, user_id: str, role: str) -> None:
    """
    Set PostgreSQL session-local variables for RLS policies.
    Must be called inside an active transaction.
    """
    await session.execute(text(f"SET LOCAL app.current_user_id = '{user_id}'"))
    await session.execute(text(f"SET LOCAL app.current_role = '{role}'"))
