from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, field_validator


# ── Auth ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    password: str
    role: Literal["patient", "doctor", "admin"]
    first_name: str
    last_name: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Patient / Doctor ────────────────────────────────────────────────────────

class PatientResponse(BaseModel):
    user_id: uuid.UUID
    first_name: str
    last_name: str
    dob: date
    phone: str | None
    address: str | None

    model_config = {"from_attributes": True}


class DoctorResponse(BaseModel):
    user_id: uuid.UUID
    first_name: str
    last_name: str
    specialty: str
    license_number: str | None

    model_config = {"from_attributes": True}


# ── Appointments ────────────────────────────────────────────────────────────

class AppointmentCreate(BaseModel):
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    scheduled_at: datetime
    notes: str | None = None


class AppointmentResponse(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    scheduled_at: datetime
    status: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Documents ───────────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    filename: str
    ingestion_status: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


# ── Clinical / Patient Notes ─────────────────────────────────────────────────

class ClinicalNoteResponse(BaseModel):
    id: uuid.UUID
    appointment_id: uuid.UUID
    soap_text: str
    signed_at: datetime | None
    ingestion_status: str

    model_config = {"from_attributes": True}


class PatientNoteResponse(BaseModel):
    id: uuid.UUID
    appointment_id: uuid.UUID
    plain_text: str

    model_config = {"from_attributes": True}


# ── Chat ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Errors ───────────────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
