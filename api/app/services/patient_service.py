from __future__ import annotations

import os
import uuid
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Appointment, ClinicalNote, Document, PatientNote, Patient


async def get_patient_profile(session: AsyncSession, user_id: UUID) -> Patient | None:
    """Retrieve the patient profile for the given user_id."""
    result = await session.execute(
        select(Patient).where(Patient.user_id == user_id)
    )
    return result.scalars().first()


async def get_patient_appointments(
    session: AsyncSession, patient_id: UUID
) -> list[Appointment]:
    """Retrieve all appointments for a patient, ordered by date descending."""
    result = await session.execute(
        select(Appointment)
        .where(Appointment.patient_id == patient_id)
        .order_by(Appointment.scheduled_at.desc())
    )
    return result.scalars().all()


async def get_patient_clinical_and_patient_notes(
    session: AsyncSession, patient_id: UUID
) -> dict:
    """
    Retrieve all clinical notes and patient notes for a patient's appointments.

    Returns:
        dict with keys:
        - clinical_notes: list of ClinicalNote objects
        - patient_notes: list of PatientNote objects
    """
    # Get all appointments for this patient
    appointments_result = await session.execute(
        select(Appointment.id).where(Appointment.patient_id == patient_id)
    )
    appointment_ids = [row[0] for row in appointments_result.fetchall()]

    if not appointment_ids:
        return {"clinical_notes": [], "patient_notes": []}

    # Get clinical notes for these appointments
    clinical_notes_result = await session.execute(
        select(ClinicalNote)
        .where(ClinicalNote.appointment_id.in_(appointment_ids))
        .order_by(ClinicalNote.appointment_id.desc())
    )
    clinical_notes = clinical_notes_result.scalars().all()

    # Get patient notes for these appointments
    patient_notes_result = await session.execute(
        select(PatientNote)
        .where(PatientNote.appointment_id.in_(appointment_ids))
        .order_by(PatientNote.appointment_id.desc())
    )
    patient_notes = patient_notes_result.scalars().all()

    return {
        "clinical_notes": clinical_notes,
        "patient_notes": patient_notes,
    }


async def get_patient_documents(
    session: AsyncSession, patient_id: UUID
) -> list[Document]:
    """Retrieve all documents for a patient, ordered by upload date descending."""
    result = await session.execute(
        select(Document)
        .where(Document.patient_id == patient_id)
        .order_by(Document.uploaded_at.desc())
    )
    return result.scalars().all()


async def upload_document(
    session: AsyncSession,
    patient_id: UUID,
    filename: str,
    file_bytes: bytes,
) -> Document:
    """
    Upload a document for a patient.

    Args:
        session: Database session
        patient_id: UUID of the patient
        filename: Original filename
        file_bytes: File contents as bytes

    Returns:
        Created Document object
    """
    # Create storage directory if it doesn't exist
    storage_dir = Path("storage/documents") / str(patient_id)
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique document ID and storage path
    doc_id = uuid.uuid4()
    storage_path = storage_dir / f"{doc_id}.pdf"

    # Save file to disk
    with open(storage_path, "wb") as f:
        f.write(file_bytes)

    # Create document record in database
    document = Document(
        id=doc_id,
        patient_id=patient_id,
        filename=filename,
        storage_path=str(storage_path),
        ingestion_status="pending",
    )

    session.add(document)
    await session.flush()  # Flush to get the created_at timestamp

    return document
