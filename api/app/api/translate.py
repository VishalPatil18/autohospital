from __future__ import annotations

# Translation endpoints are served via /patients/me/documents/{id}/translate
# in patients.py. This module re-exports a router for include compatibility.

from fastapi import APIRouter

router = APIRouter(tags=["translate"])

# Placeholder router — actual translate endpoint lives in patients.py
# Add standalone translate routes here in Phase 3 if needed.
