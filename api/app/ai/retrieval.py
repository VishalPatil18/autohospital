from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed
from app.db.models import DocumentChunk
from app.db.session import AsyncSessionLocal


@dataclass
class Chunk:
    text: str
    patient_id: UUID
    source_type: str
    source_id: UUID


async def retrieve(query: str, patient_ids: list[UUID], k: int = 8) -> list[Chunk]:
    """
    Retrieve the top-k most relevant document chunks for a query, filtered by patient_ids.

    Steps:
    1. Embed the query using Voyage AI.
    2. Run pgvector cosine similarity search filtered to the given patient IDs.
    3. Return matched chunks as Chunk dataclass instances.

    Args:
        query: The search query string.
        patient_ids: List of patient UUIDs to restrict the search to.
        k: Number of top chunks to return.

    Returns:
        List of Chunk objects sorted by relevance (most relevant first).
    """
    if not patient_ids:
        return []

    # 1. Embed the query
    query_embeddings = await embed([query])
    query_vector = query_embeddings[0]

    # Format for pgvector: '[0.1, 0.2, ...]'
    vector_literal = "[" + ",".join(str(v) for v in query_vector) + "]"

    # 2. Convert patient_ids to strings for SQL
    patient_id_strings = [str(pid) for pid in patient_ids]

    async with AsyncSessionLocal() as session:
        # Use pgvector cosine distance operator (<=>)
        sql = text(
            """
            SELECT
                id,
                patient_id,
                source_type,
                source_id,
                chunk_text,
                embedding <=> CAST(:vector AS vector) AS distance
            FROM document_chunks
            WHERE patient_id = ANY(:patient_ids::uuid[])
              AND embedding IS NOT NULL
            ORDER BY distance ASC
            LIMIT :k
            """
        )

        result = await session.execute(
            sql,
            {
                "vector": vector_literal,
                "patient_ids": patient_id_strings,
                "k": k,
            },
        )
        rows = result.fetchall()

    chunks: list[Chunk] = []
    for row in rows:
        chunks.append(
            Chunk(
                text=row.chunk_text,
                patient_id=UUID(str(row.patient_id)),
                source_type=row.source_type,
                source_id=UUID(str(row.source_id)),
            )
        )

    return chunks
