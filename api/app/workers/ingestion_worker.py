from __future__ import annotations

"""
Ingestion worker — polls `documents` and `clinical_notes` for rows with
ingestion_status='pending', chunks and embeds their text, writes to
`document_chunks`, and marks source rows 'ready' or 'failed'.

Run as a standalone process:
    python -m app.workers.ingestion_worker

The worker runs in an infinite loop with a 2-second sleep between cycles.
Each row is retried up to MAX_RETRIES times before being marked 'failed'.
"""

import asyncio
import logging
import sys
import uuid
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

# Allow running as `python -m app.workers.ingestion_worker` from api/
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.ai.chunking import chunk_text
from app.ai.embeddings import embed
from app.db.models import Appointment, ClinicalNote, Document, DocumentChunk
from app.db.session import AsyncSessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] ingestion_worker: %(message)s",
)
log = logging.getLogger(__name__)

BATCH_SIZE = 20
SLEEP_SECONDS = 2
MAX_RETRIES = 3


async def _process_document(session: AsyncSession, doc: Document) -> None:
    """Extract text from a Document file, chunk, embed, and insert chunks."""
    storage_path = Path(doc.storage_path)

    if not storage_path.exists():
        raise FileNotFoundError(f"Storage path not found: {storage_path}")

    # Extract text
    suffix = storage_path.suffix.lower()
    if suffix == ".pdf":
        import pypdf  # lazy import — only PDF docs need it

        reader = pypdf.PdfReader(str(storage_path))
        pages = [page.extract_text() or "" for page in reader.pages]
        raw_text = "\n".join(pages)
    else:
        raw_text = storage_path.read_text(encoding="utf-8", errors="replace")

    raw_text = raw_text.strip()
    if not raw_text:
        log.warning("Document %s produced empty text — skipping chunk insert", doc.id)
        return

    await _insert_chunks(
        session=session,
        patient_id=doc.patient_id,
        source_type="document",
        source_id=doc.id,
        text=raw_text,
    )


async def _process_clinical_note(session: AsyncSession, note: ClinicalNote) -> None:
    """Chunk and embed a ClinicalNote's SOAP text; look up patient_id via appointment."""
    # Resolve patient_id through the appointment
    result = await session.execute(
        select(Appointment.patient_id).where(Appointment.id == note.appointment_id)
    )
    row = result.one_or_none()
    if row is None:
        raise ValueError(f"Appointment {note.appointment_id} not found for note {note.id}")

    patient_id = row[0]
    raw_text = note.soap_text.strip()

    if not raw_text:
        log.warning("ClinicalNote %s has empty soap_text — skipping", note.id)
        return

    await _insert_chunks(
        session=session,
        patient_id=patient_id,
        source_type="clinical_note",
        source_id=note.id,
        text=raw_text,
    )


async def _insert_chunks(
    session: AsyncSession,
    patient_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID,
    text: str,
) -> None:
    """Chunk text, embed in batch, and bulk-insert DocumentChunk rows."""
    chunks = chunk_text(text)
    if not chunks:
        return

    embeddings = await embed(chunks)

    chunk_rows = [
        DocumentChunk(
            id=uuid.uuid4(),
            patient_id=patient_id,
            source_type=source_type,
            source_id=source_id,
            chunk_text=chunk,
            embedding=emb,
        )
        for chunk, emb in zip(chunks, embeddings)
    ]
    session.add_all(chunk_rows)
    # Flush so rows are written before the caller commits
    await session.flush()

    log.info(
        "Ingested %d chunks for %s %s (patient %s)",
        len(chunk_rows),
        source_type,
        source_id,
        patient_id,
    )


async def _run_cycle() -> None:
    """Process one batch of pending documents and clinical notes."""
    async with AsyncSessionLocal() as session:
        # --- Documents ---
        doc_result = await session.execute(
            select(Document)
            .where(Document.ingestion_status == "pending")
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        docs = doc_result.scalars().all()

        for doc in docs:
            try:
                await _process_document(session, doc)
                doc.ingestion_status = "ready"
                log.info("Document %s → ready", doc.id)
            except Exception as exc:
                retry_count = _bump_retry(doc)
                if retry_count >= MAX_RETRIES:
                    doc.ingestion_status = "failed"
                    log.error("Document %s → failed after %d retries: %s", doc.id, retry_count, exc)
                else:
                    log.warning("Document %s retry %d: %s", doc.id, retry_count, exc)

        # --- Clinical Notes ---
        note_result = await session.execute(
            select(ClinicalNote)
            .where(ClinicalNote.ingestion_status == "pending")
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        notes = note_result.scalars().all()

        for note in notes:
            try:
                await _process_clinical_note(session, note)
                note.ingestion_status = "ready"
                log.info("ClinicalNote %s → ready", note.id)
            except Exception as exc:
                retry_count = _bump_retry(note)
                if retry_count >= MAX_RETRIES:
                    note.ingestion_status = "failed"
                    log.error("ClinicalNote %s → failed after %d retries: %s", note.id, retry_count, exc)
                else:
                    log.warning("ClinicalNote %s retry %d: %s", note.id, retry_count, exc)

        await session.commit()


def _bump_retry(row: Document | ClinicalNote) -> int:
    """Increment an in-memory retry counter stored on the row's __dict__."""
    count = getattr(row, "_retry_count", 0) + 1
    row._retry_count = count  # type: ignore[attr-defined]
    return count


async def main() -> None:
    log.info("Ingestion worker started (batch=%d, sleep=%ds)", BATCH_SIZE, SLEEP_SECONDS)
    while True:
        try:
            await _run_cycle()
        except Exception as exc:
            log.error("Unhandled error in run cycle: %s", exc, exc_info=True)
        await asyncio.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
