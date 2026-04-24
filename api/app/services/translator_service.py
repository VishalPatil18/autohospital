from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import AnthropicClient
from app.db.models import Document


async def translate_document(
    session: AsyncSession,
    document_id: UUID,
    patient_id: UUID,
) -> str:
    """
    Translate a document using Claude and cache the result.

    Steps:
    1. Load the document from database
    2. Verify ownership (patient_id match)
    3. Extract text from PDF file
    4. Call AnthropicClient.translate_document
    5. Cache result in document.translation
    6. Return the translation

    Args:
        session: Database session
        document_id: UUID of the document to translate
        patient_id: UUID of the patient (for ownership verification)

    Returns:
        The translated text
    """
    # Load document
    result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalars().first()

    if not document:
        raise ValueError(f"Document not found: {document_id}")

    # Verify ownership
    if document.patient_id != patient_id:
        raise PermissionError(
            "You do not have permission to translate this document")

    # Return cached translation if available
    if document.translation:
        return document.translation

    # Extract PDF text
    try:
        from pypdf import PdfReader

        pdf_path = Path(document.storage_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"Document file not found: {pdf_path}")

        reader = PdfReader(pdf_path)
        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text.strip():
                pages_text.append(text)

        extracted_text = "\n\n".join(pages_text)
        if not extracted_text.strip():
            raise ValueError("No text could be extracted from the PDF")

    except ImportError:
        raise RuntimeError("pypdf library not installed")
    except Exception as err:
        raise RuntimeError(f"Failed to extract PDF text: {str(err)}")

    # Translate using Claude
    client = AnthropicClient()
    translation = await client.translate_document(extracted_text)

    # Cache result
    document.translation = translation
    session.add(document)
    await session.flush()

    return translation
