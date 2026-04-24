from __future__ import annotations

import re
import unicodedata
from uuid import UUID

from app.ai.retrieval import Chunk

# Patterns that indicate prompt injection attempts in retrieved content
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(?:(?:all|previous|prior)\s+)+instructions?", re.I),
    re.compile(r"\bsystem\s*:", re.I),
    re.compile(r"you\s+are\s+now\b", re.I),
    re.compile(r"disregard\s+(previous|prior|all)", re.I),
    re.compile(r"new\s+instructions?\s*:", re.I),
    re.compile(r"override\s+(previous|prior)\s+instructions?", re.I),
    re.compile(r"forget\s+(previous|prior|all)", re.I),
    re.compile(r"act\s+as\s+(if\s+you\s+are|a\b)", re.I),
    re.compile(r"reveal\s+(patient|user|data|record)", re.I),
    re.compile(r"jailbreak", re.I),
]

# Zero-width and invisible Unicode characters used in injection attacks
_INVISIBLE_CHARS = re.compile(
    r"[​‌‍‎‏‪-‮⁠-⁤﻿]"
)


def sanitize_chunks(chunks: list[Chunk]) -> list[str]:
    """
    Sanitize retrieved chunks to neutralize prompt injection patterns.

    Replaces injection patterns with [redacted-instruction] so the seam is
    visible to the LLM rather than silently removed.

    Returns cleaned chunk text strings (not Chunk objects).
    """
    sanitized: list[str] = []
    for chunk in chunks:
        text = chunk.text

        # Strip invisible / zero-width characters used in steganographic attacks
        text = _INVISIBLE_CHARS.sub("", text)

        # Normalize Unicode to NFC to catch homoglyph attacks
        text = unicodedata.normalize("NFC", text)

        # Replace injection patterns
        for pattern in _INJECTION_PATTERNS:
            text = pattern.sub("[redacted-instruction]", text)

        sanitized.append(text)
    return sanitized


def scope_header(role: str, patient_ids: list[UUID]) -> str:
    """
    Return a scope-restriction block injected as the first context chunk.

    This is prepended to the retrieval chunks so it lands in the LLM's
    system-level context (via AnthropicClient.chat's context_section).
    """
    pid_list = ", ".join(str(pid) for pid in patient_ids)
    if role == "doctor":
        return (
            "[SCOPE RESTRICTION — MANDATORY]\n"
            f"You are assisting a licensed physician. Your knowledge is limited to "
            f"information retrieved from the medical records of the following patient(s): {pid_list}. "
            "Do NOT reveal, infer, or speculate about any other patient's data. "
            "If asked about a patient not in this list, refuse and explain the scope restriction. "
            "Always cite which retrieved chunk supports each clinical claim."
        )
    else:
        return (
            "[SCOPE RESTRICTION — MANDATORY]\n"
            f"You are assisting a patient (user {pid_list}). "
            "Your knowledge is limited to information retrieved from this patient's own medical records. "
            "Do NOT speculate beyond the provided context. "
            "NEVER provide a diagnosis. Use language like 'this value appears outside the typical range' "
            "rather than 'you have [condition]'. "
            "For any treatment or medication question, recommend consulting a licensed clinician."
        )
