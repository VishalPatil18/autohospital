from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.schemas import (
    AppointmentResponse,
    ClinicalNoteResponse,
    DocumentResponse,
    PatientNoteResponse,
    PatientResponse,
)
from app.db.session import get_db
from app.services import patient_service, translator_service

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/me", response_model=PatientResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get the current patient's profile."""
    patient = await patient_service.get_patient_profile(session, current_user["id"])
    if not patient:
        raise HTTPException(
            status_code=404, detail="Patient profile not found")
    return patient


@router.get("/me/appointments", response_model=list[AppointmentResponse])
async def get_my_appointments(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get all appointments for the current patient."""
    appointments = await patient_service.get_patient_appointments(
        session, current_user["id"]
    )
    return appointments


@router.get("/me/notes")
async def get_my_notes(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get all clinical and patient notes for the current patient's appointments."""
    notes_data = await patient_service.get_patient_clinical_and_patient_notes(
        session, current_user["id"]
    )

    clinical_notes = [
        ClinicalNoteResponse.model_validate(note)
        for note in notes_data["clinical_notes"]
    ]
    patient_notes = [
        PatientNoteResponse.model_validate(note)
        for note in notes_data["patient_notes"]
    ]

    return {
        "clinical_notes": clinical_notes,
        "patient_notes": patient_notes,
    }


@router.get("/me/documents", response_model=list[DocumentResponse])
async def get_my_documents(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get all documents uploaded by the current patient."""
    documents = await patient_service.get_patient_documents(session, current_user["id"])
    return documents


@router.post("/me/documents", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Upload a PDF document for the current patient.

    - Validates MIME type (must be application/pdf)
    - Stores file on disk under storage/documents/{patient_id}/{doc_id}.pdf
    - Inserts document row with ingestion_status='pending' for worker processing
    - Returns document metadata
    """
    # Validate MIME type
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted",
        )

    # Read file bytes
    try:
        file_bytes = await file.read()
    except Exception as err:
        raise HTTPException(
            status_code=400, detail=f"Failed to read file: {str(err)}")

    if not file_bytes:
        raise HTTPException(status_code=400, detail="File is empty")

    # Validate PDF signature (first 4 bytes should be %PDF)
    if not file_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=400,
            detail="Invalid PDF file",
        )

    # Upload document
    try:
        document = await patient_service.upload_document(
            session,
            current_user["id"],
            file.filename or "document.pdf",
            file_bytes,
        )
        await session.commit()
        return document
    except Exception as err:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload document: {str(err)}",
        )


@router.post("/me/documents/{document_id}/translate")
async def translate_document(
    document_id: UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Translate a patient's document using Claude.

    - Extracts text from the PDF
    - Translates to plain English with medical glossary
    - Caches result in document.translation for future requests
    - Returns the translation
    """
    try:
        translation = await translator_service.translate_document(
            session,
            document_id,
            current_user["id"],
        )
        await session.commit()
        return {"translation": translation}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except (FileNotFoundError, RuntimeError) as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Translation failed: {str(err)}",
        )
