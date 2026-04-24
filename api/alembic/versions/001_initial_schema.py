"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-24 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Create pgcrypto extension (for gen_random_uuid in older PG)
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # 3. Create app_role role if not exists
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_role') THEN
                CREATE ROLE app_role NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE;
            END IF;
        END
        $$;
        """
    )

    # 4. Create tables

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "role",
            sa.String(),
            sa.CheckConstraint("role IN ('patient', 'doctor', 'admin')", name="users_role_check"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # patients
    op.create_table(
        "patients",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("dob", sa.Date(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
    )

    # doctors
    op.create_table(
        "doctors",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("specialty", sa.String(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("license_number", sa.String(), nullable=True),
    )

    # care_team
    op.create_table(
        "care_team",
        sa.Column(
            "doctor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doctors.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # appointments
    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "doctor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doctors.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            sa.CheckConstraint(
                "status IN ('scheduled', 'completed', 'cancelled')",
                name="appointments_status_check",
            ),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column(
            "ingestion_status",
            sa.String(),
            sa.CheckConstraint(
                "ingestion_status IN ('pending', 'ready', 'failed')",
                name="documents_ingestion_status_check",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # clinical_notes
    op.create_table(
        "clinical_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("soap_text", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingestion_status", sa.String(), nullable=False, server_default="pending"),
    )

    # patient_notes
    op.create_table(
        "patient_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plain_text", sa.Text(), nullable=False),
    )

    # transcripts
    op.create_table(
        "transcripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # document_chunks (with vector column)
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),  # created as vector(1024) below
    )
    # Alter column to proper vector type (pgvector)
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1024) USING embedding::vector(1024)")

    # chat_messages
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            sa.String(),
            sa.CheckConstraint("role IN ('user', 'assistant')", name="chat_messages_role_check"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 5. HNSW index for cosine similarity search on document_chunks
    op.execute(
        "CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops)"
    )

    # 6. Enable RLS on sensitive tables
    for table in ("documents", "document_chunks", "clinical_notes", "patient_notes", "chat_messages"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # 7. RLS policies

    # documents
    op.execute(
        """
        CREATE POLICY patient_self_access ON documents
            FOR ALL
            TO PUBLIC
            USING (
                patient_id::text = current_setting('app.current_user_id', true)
                AND current_setting('app.current_role', true) = 'patient'
            )
        """
    )
    op.execute(
        """
        CREATE POLICY doctor_care_team_access ON documents
            FOR ALL
            TO PUBLIC
            USING (
                current_setting('app.current_role', true) = 'doctor'
                AND patient_id IN (
                    SELECT patient_id FROM care_team
                    WHERE doctor_id::text = current_setting('app.current_user_id', true)
                )
            )
        """
    )

    # document_chunks
    op.execute(
        """
        CREATE POLICY patient_self_access ON document_chunks
            FOR ALL
            TO PUBLIC
            USING (
                patient_id::text = current_setting('app.current_user_id', true)
                AND current_setting('app.current_role', true) = 'patient'
            )
        """
    )
    op.execute(
        """
        CREATE POLICY doctor_care_team_access ON document_chunks
            FOR ALL
            TO PUBLIC
            USING (
                current_setting('app.current_role', true) = 'doctor'
                AND patient_id IN (
                    SELECT patient_id FROM care_team
                    WHERE doctor_id::text = current_setting('app.current_user_id', true)
                )
            )
        """
    )

    # clinical_notes (access via appointment → patient)
    op.execute(
        """
        CREATE POLICY patient_self_access ON clinical_notes
            FOR ALL
            TO PUBLIC
            USING (
                current_setting('app.current_role', true) = 'patient'
                AND appointment_id IN (
                    SELECT id FROM appointments
                    WHERE patient_id::text = current_setting('app.current_user_id', true)
                )
            )
        """
    )
    op.execute(
        """
        CREATE POLICY doctor_care_team_access ON clinical_notes
            FOR ALL
            TO PUBLIC
            USING (
                current_setting('app.current_role', true) = 'doctor'
                AND appointment_id IN (
                    SELECT id FROM appointments
                    WHERE doctor_id::text = current_setting('app.current_user_id', true)
                )
            )
        """
    )

    # patient_notes
    op.execute(
        """
        CREATE POLICY patient_self_access ON patient_notes
            FOR ALL
            TO PUBLIC
            USING (
                current_setting('app.current_role', true) = 'patient'
                AND appointment_id IN (
                    SELECT id FROM appointments
                    WHERE patient_id::text = current_setting('app.current_user_id', true)
                )
            )
        """
    )
    op.execute(
        """
        CREATE POLICY doctor_care_team_access ON patient_notes
            FOR ALL
            TO PUBLIC
            USING (
                current_setting('app.current_role', true) = 'doctor'
                AND appointment_id IN (
                    SELECT id FROM appointments
                    WHERE doctor_id::text = current_setting('app.current_user_id', true)
                )
            )
        """
    )

    # chat_messages
    op.execute(
        """
        CREATE POLICY patient_self_access ON chat_messages
            FOR ALL
            TO PUBLIC
            USING (
                user_id::text = current_setting('app.current_user_id', true)
                AND current_setting('app.current_role', true) = 'patient'
            )
        """
    )
    op.execute(
        """
        CREATE POLICY doctor_care_team_access ON chat_messages
            FOR ALL
            TO PUBLIC
            USING (
                current_setting('app.current_role', true) = 'doctor'
                AND user_id IN (
                    SELECT patient_id FROM care_team
                    WHERE doctor_id::text = current_setting('app.current_user_id', true)
                )
            )
        """
    )

    # 8. Helper function for setting user context
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_app_user_context(p_user_id text, p_role text)
        RETURNS void AS $$
        BEGIN
            PERFORM set_config('app.current_user_id', p_user_id, true);
            PERFORM set_config('app.current_role', p_role, true);
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    # Drop RLS policies
    for table in ("documents", "document_chunks", "clinical_notes", "patient_notes", "chat_messages"):
        op.execute(f"DROP POLICY IF EXISTS patient_self_access ON {table}")
        op.execute(f"DROP POLICY IF EXISTS doctor_care_team_access ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP FUNCTION IF EXISTS set_app_user_context(text, text)")

    # Drop tables in reverse dependency order
    op.drop_table("audit_events")
    op.drop_table("chat_messages")
    op.drop_table("document_chunks")
    op.drop_table("transcripts")
    op.drop_table("patient_notes")
    op.drop_table("clinical_notes")
    op.drop_table("documents")
    op.drop_table("appointments")
    op.drop_table("care_team")
    op.drop_table("doctors")
    op.drop_table("patients")
    op.drop_table("users")
