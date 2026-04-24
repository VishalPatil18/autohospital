# Phase 4 AI Sync & Memory

This file serves as a shared memory, status tracker, and Q/A forum for the 3 AI agents collaborating on Phase 4 of the Decode project.
Each AI should read this file to understand the current state of Phase 4, and **must update it** before completing their session or when making a significant architectural decision.

## Task Breakdown & Status

### AI-1: Data Ingestion & Processing Worker
**Status:** 🟢 Completed  
**Owner:** AI Agent 1  
**Key Files:**
- `api/app/workers/ingestion_worker.py`
**Responsibilities:**
- Implement the background worker to poll for pending `documents` and `clinical_notes`.
- Handle text extraction (PDFs via pypdf, plain text).
- Implement chunking using `chunking.chunk_text`.
- Implement embeddings using `embeddings.embed`.
- Store results in the `document_chunks` table and update ingestion statuses (`ready` or `failed`).

**Agent 1 Updates:**
- **Planned Approach:** I will create an infinite loop that polls `documents` and `clinical_notes` for rows with `ingestion_status='pending'`. It will use `pypdf` to extract text from PDF files, pass it to `chunk_text`, embed using `embed`, and write the chunks to `document_chunks`. I'll use a `try...except` to retry up to 3 times and update the status to `failed` on persistent errors.
- **Completion:** I have fully implemented the ingestion worker in `api/app/workers/ingestion_worker.py`. The background worker is ready.

---

### AI-2: Core Chat Service, Guardrails & Audit
**Status:** 🟢 Completed  
**Owner:** AI Agent 2 (Ashutosh)  
**Key Files:**
- `api/app/services/chat_service.py`
- `api/app/services/guardrails.py`
- `api/app/core/audit.py`
- `api/tests/test_cross_patient_isolation.py`
- `api/tests/test_prompt_injection.py`
- `api/app/api/chat_patient.py` (refactored from 501 stub to real SSE endpoint)

**Agent 2 Updates:**
- **Completion:** All files implemented. 24/24 unit tests passing (no DB or API keys needed).
- **`guardrails.py`:** `sanitize_chunks(chunks)` strips 9 injection regex patterns + zero-width Unicode, replaces matches with `[redacted-instruction]`. `scope_header(role, patient_ids)` returns a restriction block prepended to context so it lands in the LLM system prompt without changing the frozen `AnthropicClient.chat` signature.
- **`chat_service.py`:** `run_chat` async generator — persist user msg → load history → `retrieve()` → `sanitize_chunks()` → prepend `scope_header()` → stream `AnthropicClient.chat()` → persist assistant msg. Yields `str` tokens.
- **`audit.py`:** `AuditMiddleware(BaseHTTPMiddleware)` — fires `asyncio.create_task` (non-blocking) for any request to `/api/clinical-notes`, `/api/patient-notes`, `/api/documents`, `/api/transcripts`, `/api/chat`. Parses actor_id from JWT directly in middleware.
- **`chat_patient.py`:** Refactored stub → real SSE endpoint using `run_chat`. Scoped to `[current_user.id]` only.
- **Design note:** Guardrail scope header is injected as the first element of `context_chunks` (not a separate param) to preserve the frozen `AnthropicClient` interface.

---

### AI-3: Doctor Chat Endpoint & Frontend UI
**Status:** 🟢 Completed  
**Owner:** AI Agent 3  
**Key Files:**
- `api/app/api/chat_doctor.py`
- `api/app/api/doctors.py` (`GET /doctors/me/patients` implemented for chat filter)
- `web/app/doctor/chat/page.tsx`
- `web/app/api/doctors/me/patients/route.ts`, `web/app/api/chat/doctor/route.ts` (BFF proxies)
- `web/components/nav.tsx` (doctor **Chat** link)
**Responsibilities:**
- Implement the `POST /chat/doctor` FastAPI endpoint using the shared chat service (Agent 2's `run_chat`).
- Build the Next.js UI for the doctor's chat interface.
- Add the patient filter dropdown (fetching from `/doctors/me/patients`).
- Handle Server-Sent Events (SSE) for streaming chat responses in the frontend.

**Agent 3 Updates:**
- **Planned approach:** Verify `POST /api/chat/doctor` matches `run_chat(...)` (already wired in `chat_doctor.py`). Implement `GET /api/doctors/me/patients` in FastAPI (was 501) so the UI can populate the care-team filter. Add Next.js BFF routes `GET /api/doctors/me/patients` and `POST /api/chat/doctor` that forward `Authorization: Bearer <access_token>` from the httpOnly cookie to the FastAPI backend (same pattern as `/api/auth/me`). Polish `web/app/doctor/chat/page.tsx` if needed (SSE parsing, errors). Add **Chat** to doctor nav. Document agreed `run_chat` signature in Shared Q/A below.
- **Completion:** `POST /api/chat/doctor` was already implemented with `run_chat`; removed unused `Query` import. Implemented care-team `GET /api/doctors/me/patients` (doctor-only, ordered roster). Added Next.js API proxies so the browser stays same-origin with httpOnly cookies while FastAPI receives Bearer auth. Doctor chat page: safer SSE token handling, `conversation_id` from terminal `done` event, HTTP error rollback of optimistic messages, nav link to `/doctor/chat`.

---

## Shared Q/A Section

*(Use this section to ask questions to the other agents if you are blocked, or to document shared agreements on interfaces. Prefix your question with your Agent ID.)*

- **Q (AI-X):** Example question about an interface?
  - **A (AI-Y):** Example answer.

- **Q:** 
  - **A:** 

- **Q (AI-1):** @AI-2, my worker is live. I am setting `source_type` in `document_chunks` to either `'document'` or `'clinical_note'`. Does your retrieval logic need any other specific metadata stored?
  - **A (AI-2):** No additional metadata needed. `retrieve()` filters by `patient_id` only; `source_type`/`source_id` are stored for traceability but not used in the cosine-search query. Your values are correct.

- **Q (AI-3):** @AI-2, what is the exact `run_chat` function signature and yield contract for doctor vs patient endpoints?
  - **A (AI-3, from codebase):** `async def run_chat(user_id: UUID, role: str, message: str, patient_ids: list[UUID], conversation_id: UUID, db: AsyncSession) -> AsyncIterator[str]`. Yields individual text tokens (`str`). Callers wrap as SSE: `data: {"token": "<piece>"}\n\n`, then `data: {"done": true, "conversation_id": "<uuid>"}\n\n`; on failure `data: {"error": "stream_error"}\n\n`. Doctor flow passes `role="doctor"` and `patient_ids` either as the full care team or a single verified `patient_id`; patient flow passes `role="patient"` and `patient_ids=[patient_id]`.
