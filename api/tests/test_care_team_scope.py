"""
Contract test: a doctor can only query patients in their care team.
POST /api/chat/doctor with a patient_id not in the doctor's care team must 403.
"""
from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_chat_doctor_without_auth_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/chat/doctor",
            json={"message": "hello"},
        )
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_doctor_cannot_query_out_of_care_team_patient(doctor_token: str):
    """
    A doctor sending patient_id that is NOT in their care team must receive 403,
    not an empty result set.

    `doctor_token` fixture must be provided by conftest.py (integration only).
    """
    out_of_team_patient_id = str(uuid.uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/chat/doctor",
            json={"message": "What is this patient's A1C?", "patient_id": out_of_team_patient_id},
            headers={"Authorization": f"Bearer {doctor_token}"},
        )

    assert response.status_code == 403, (
        f"Expected 403 for out-of-care-team patient, got {response.status_code}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_doctor_with_no_care_team_patients_gets_403(doctor_token_no_patients: str):
    """
    A doctor with an empty care team cannot initiate any chat.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/chat/doctor",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {doctor_token_no_patients}"},
        )
    assert response.status_code == 403
