from __future__ import annotations

import uuid
from datetime import datetime, date

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(
        String,
        CheckConstraint("role IN ('patient', 'doctor', 'admin')",
                        name="users_role_check"),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True),
                        server_default=func.now(), nullable=False)

    patient_profile = relationship(
        "Patient", back_populates="user", uselist=False)
    doctor_profile = relationship(
        "Doctor", back_populates="user", uselist=False)
    chat_messages = relationship("ChatMessage", back_populates="user")
    audit_events = relationship("AuditEvent", back_populates="actor")


class Patient(Base):
    __tablename__ = "patients"

    user_id = Column(UUID(as_uuid=True), ForeignKey(
        "users.id", ondelete="CASCADE"), primary_key=True)
    dob = Column(Date, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)

    user = relationship("User", back_populates="patient_profile")
    care_team_entries = relationship("CareTeam", back_populates="patient")
    appointments = relationship("Appointment", back_populates="patient")
    documents = relationship("Document", back_populates="patient")
    document_chunks = relationship("DocumentChunk", back_populates="patient")


class Doctor(Base):
    __tablename__ = "doctors"

    user_id = Column(UUID(as_uuid=True), ForeignKey(
        "users.id", ondelete="CASCADE"), primary_key=True)
    specialty = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    license_number = Column(String, nullable=True)

    user = relationship("User", back_populates="doctor_profile")
    care_team_entries = relationship("CareTeam", back_populates="doctor")
    appointments = relationship("Appointment", back_populates="doctor")


class CareTeam(Base):
    __tablename__ = "care_team"

    doctor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("doctors.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.user_id", ondelete="CASCADE"),
        primary_key=True,
    )

    doctor = relationship("Doctor", back_populates="care_team_entries")
    patient = relationship("Patient", back_populates="care_team_entries")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey(
        "patients.user_id", ondelete="CASCADE"), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey(
        "doctors.user_id", ondelete="CASCADE"), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(
        String,
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled')",
            name="appointments_status_check",
        ),
        nullable=False,
        default="scheduled",
        server_default="scheduled",
    )
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True),
                        server_default=func.now(), nullable=False)

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    clinical_notes = relationship("ClinicalNote", back_populates="appointment")
    patient_notes = relationship("PatientNote", back_populates="appointment")
    transcripts = relationship("Transcript", back_populates="appointment")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey(
        "patients.user_id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    ingestion_status = Column(
        String,
        CheckConstraint(
            "ingestion_status IN ('pending', 'ready', 'failed')",
            name="documents_ingestion_status_check",
        ),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    translation = Column(Text, nullable=True)  # Cached translation result
    uploaded_at = Column(DateTime(timezone=True),
                         server_default=func.now(), nullable=False)

    patient = relationship("Patient", back_populates="documents")


class ClinicalNote(Base):
    __tablename__ = "clinical_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey(
        "appointments.id", ondelete="CASCADE"), nullable=False)
    soap_text = Column(Text, nullable=False)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    ingestion_status = Column(
        String,
        nullable=False,
        default="pending",
        server_default="pending",
    )

    appointment = relationship("Appointment", back_populates="clinical_notes")


class PatientNote(Base):
    __tablename__ = "patient_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey(
        "appointments.id", ondelete="CASCADE"), nullable=False)
    plain_text = Column(Text, nullable=False)

    appointment = relationship("Appointment", back_populates="patient_notes")


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey(
        "appointments.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True),
                        server_default=func.now(), nullable=False)

    appointment = relationship("Appointment", back_populates="transcripts")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey(
        "patients.user_id", ondelete="CASCADE"), nullable=False)
    source_type = Column(String, nullable=False)
    source_id = Column(UUID(as_uuid=True), nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=True)

    patient = relationship("Patient", back_populates="document_chunks")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), nullable=False)
    role = Column(
        String,
        CheckConstraint("role IN ('user', 'assistant')",
                        name="chat_messages_role_check"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True),
                        server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="chat_messages")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id = Column(UUID(as_uuid=True), ForeignKey(
        "users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    ip = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True),
                        server_default=func.now(), nullable=False)

    actor = relationship("User", back_populates="audit_events")
