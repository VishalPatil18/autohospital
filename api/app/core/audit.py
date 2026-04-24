from __future__ import annotations

import asyncio
import logging
import uuid

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.db.session import AsyncSessionLocal

log = logging.getLogger(__name__)

# Paths whose access must be recorded in audit_events
_AUDITED_PREFIXES = (
    "/api/clinical-notes",
    "/api/patient-notes",
    "/api/documents",
    "/api/transcripts",
    "/api/chat",
)


def _resource_type_from_path(path: str) -> str:
    for prefix in _AUDITED_PREFIXES:
        if path.startswith(prefix):
            return prefix.lstrip("/api/").split("/")[0]
    return "unknown"


def _extract_user_id(request: Request) -> str | None:
    """Parse JWT from Authorization header or cookie; return sub claim or None."""
    token: str | None = None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


async def _write_audit_event(
    actor_id: str | None,
    action: str,
    resource_type: str,
    ip: str | None,
) -> None:
    """Open a short-lived DB session and insert one audit_events row."""
    from app.db.models import AuditEvent

    try:
        async with AsyncSessionLocal() as session:
            event = AuditEvent(
                id=uuid.uuid4(),
                actor_id=uuid.UUID(actor_id) if actor_id else None,
                action=action,
                resource_type=resource_type,
                resource_id=None,
                ip=ip,
            )
            session.add(event)
            await session.commit()
    except Exception as exc:
        log.error("Failed to write audit event: %s", exc)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Records every request to clinical resource paths in `audit_events`.

    The write is fire-and-forget (asyncio.create_task) so it never adds
    latency to the response.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        path = request.url.path
        if any(path.startswith(prefix) for prefix in _AUDITED_PREFIXES):
            actor_id = _extract_user_id(request)
            action = f"{request.method} {path}"
            resource_type = _resource_type_from_path(path)
            ip = (request.client.host if request.client else None)

            # Fire-and-forget — do not await; never block the response
            asyncio.create_task(
                _write_audit_event(actor_id, action, resource_type, ip)
            )

        return response
