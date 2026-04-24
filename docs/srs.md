# Software Requirements Specification: Decode

**Version:** 1.0 (Hackathon Scope)
**Stack:** Next.js (Frontend) + Python / FastAPI (Backend) + PostgreSQL + pgvector
**Team:** Vishal, Darsh, Ashutosh

---

## 1. System Architecture

Decode follows a three-tier client-server model. The Next.js frontend is the sole client surface for both patient and doctor personas, rendered via SSR for authenticated pages and CSR for interactive components (chatbot, live scribe). All business logic, AI orchestration, and data access is consolidated in a single Python FastAPI backend, which is the only service permitted to touch the database or external AI providers. PostgreSQL serves as the system of record and the vector store (via the `pgvector` extension), eliminating the need for a separate vector database.

**Request flow:**

1. Browser (Next.js) authenticates the user and stores the JWT in an httpOnly cookie.
2. Next.js forwards requests to FastAPI with the JWT in the `Authorization` header.
3. FastAPI validates the JWT, sets per-request PostgreSQL session variables (`app.current_user_id`, `app.current_role`), and executes queries. Row-Level Security enforces data isolation at the DB layer.
4. For AI workloads, FastAPI calls Deepgram (streaming audio) and Anthropic (LLM) over HTTPS, then persists artifacts back to Postgres.
5. Real-time features (Ambient Scribe live transcript) use a WebSocket between the browser and FastAPI; FastAPI proxies audio frames to Deepgram and streams transcript tokens back.

No Docker, no Kubernetes. FastAPI runs under `uvicorn` as a systemd service (or `pm2`), Next.js runs via `next start`, Postgres runs natively.

```
┌─────────────┐     HTTPS/WSS      ┌──────────────┐     SQL + RLS      ┌─────────────┐
│  Next.js    │  ───────────────▶  │   FastAPI    │  ────────────────▶ │ PostgreSQL  │
│  (Browser)  │  ◀───── SSE ─────  │  (uvicorn)   │  ◀─────────────── │ + pgvector  │
└─────────────┘                    └──────┬───────┘                    └─────────────┘
                                          │
                                          ├──▶ Deepgram (streaming ASR)
                                          ├──▶ Anthropic Claude (LLM)
                                          └──▶ Voyage AI (embeddings)
```

---

## 2. Functional Requirements

### 2.1 Ambient Scribe (Doctor Module)

**Inputs:** live microphone audio from the doctor's browser during a consultation, plus `patient_id` and `appointment_id` context selected before recording starts.

**Pipeline:**
1. Browser captures audio via `MediaRecorder` (PCM 16 kHz) and streams chunks over a WebSocket to FastAPI (`/ws/scribe/{appointment_id}`).
2. FastAPI opens a streaming connection to Deepgram (`nova-2-medical` model, diarization enabled) and forwards audio frames bidirectionally.
3. Interim and final transcripts stream back to the browser for live display.
4. On session end, the full diarized transcript is persisted to the `transcripts` table, then sent to Claude with a structured prompt to produce two artifacts:
   - **Clinical summary** (SOAP format: Subjective, Objective, Assessment, Plan) stored as `clinical_notes`.
   - **Patient-friendly notes** (plain English, ~6th-grade reading level) stored as `patient_notes`.
5. Doctor reviews, edits, and signs off. Signed-off notes are locked (immutable, with an `edited_at` audit entry if reopened).

**Latency targets:** interim transcript < 500 ms; post-consult summary generation < 15 s for a 20-minute conversation.

### 2.2 Patient Chatbot with RAG + Guardrails

**Scope guardrail (hard constraint):** every retrieval and every LLM call is scoped to `user_id = current_patient_id`. Enforcement occurs in three layers: authorization middleware, database RLS, and a final system-prompt instruction to Claude.

**RAG pipeline:**
1. On document upload or new clinical note, the ingestion worker chunks the text (~500 tokens, 50-token overlap), generates embeddings via `voyage-3`, and stores them in `document_chunks(patient_id, chunk_text, embedding vector(1024))`.
2. At query time: embed the user question, then run
   ```sql
   SELECT chunk_text
   FROM document_chunks
   WHERE patient_id = current_setting('app.current_user_id')::uuid
   ORDER BY embedding <=> $1
   LIMIT 8;
   ```
3. Top-k chunks are assembled into a prompt with the user question and sent to Claude with a system prompt that forbids answers outside the provided context.
4. Response is streamed back to the client via SSE.

**Document translator:** patient uploads a PDF report, backend extracts text (`pypdf`), sends to Claude with a translation-to-plain-English prompt, returns annotated output with a medical term glossary.

### 2.3 Doctor CRM Dashboard

Core views: patient list (filtered to `care_team.doctor_id = current_doctor_id`), patient detail (demographics, problem list, medications, appointment history, documents, clinical notes), appointment calendar, scribe launcher.

**Doctor chatbot scope:** retrieval filtered to `patient_id IN (SELECT patient_id FROM care_team WHERE doctor_id = current_doctor_id)`. Same RAG pipeline as the patient chatbot; only the WHERE clause differs.

CRUD: create/edit patient records, schedule appointments, upload documents on behalf of a patient, review and sign Ambient Scribe outputs.

---

## 3. Data Security & Privacy Model

**Authentication:** email + password with `argon2` hashing, JWT access tokens (15 min) + refresh tokens (7 days) as httpOnly, Secure, SameSite=Strict cookies. Roles: `patient`, `doctor`, `admin`.

**Authorization — defense in depth:**

**Layer 1 — API middleware.** FastAPI dependency `get_current_user()` decodes the JWT, loads the user, and rejects on role/scope mismatch.

**Layer 2 — PostgreSQL Row-Level Security** (the non-negotiable floor):

```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY patient_self_access ON documents
  FOR ALL TO app_role
  USING (
    patient_id::text = current_setting('app.current_user_id', true)
    AND current_setting('app.current_role', true) = 'patient'
  );

CREATE POLICY doctor_care_team_access ON documents
  FOR ALL TO app_role
  USING (
    current_setting('app.current_role', true) = 'doctor'
    AND patient_id IN (
      SELECT patient_id FROM care_team
      WHERE doctor_id::text = current_setting('app.current_user_id', true)
    )
  );
```

Before every request FastAPI executes `SET LOCAL app.current_user_id = $1; SET LOCAL app.current_role = $2;` inside the transaction. The app DB user is non-superuser, so RLS cannot be bypassed.

**Layer 3 — LLM prompt constraints.** System prompts instruct Claude to refuse cross-patient inference and cite which retrieved chunk a statement came from.

**At rest:** Postgres disk encryption; sensitive columns encrypted with `pgcrypto`.
**In transit:** TLS on all hops (FastAPI to Deepgram, FastAPI to Anthropic).
**Audit log:** `audit_events(actor_id, action, resource_type, resource_id, timestamp, ip)` written on every clinical data read and every mutation.

---

## 4. API Strategy

REST + SSE + WebSocket. JSON over HTTPS. All endpoints require `Authorization: Bearer <jwt>` unless marked public.

**Auth**
- `POST /auth/register` (public)
- `POST /auth/login` (public)
- `POST /auth/refresh`
- `POST /auth/logout`

**Patient-facing**
- `GET /patients/me`
- `GET /patients/me/documents`
- `POST /patients/me/documents` (multipart upload)
- `POST /patients/me/documents/{id}/translate`
- `GET /patients/me/appointments`
- `GET /patients/me/notes`
- `POST /chat/patient` — SSE token stream

**Doctor-facing**
- `GET /doctors/me/patients`
- `GET /patients/{id}`
- `POST /patients`, `PATCH /patients/{id}`
- `GET /appointments?date=...`, `POST /appointments`, `PATCH /appointments/{id}`
- `WS /ws/scribe/{appointment_id}`
- `POST /scribe/{appointment_id}/finalize`
- `PATCH /clinical-notes/{id}`, `POST /clinical-notes/{id}/sign`
- `POST /chat/doctor` — SSE token stream

**Conventions:** `snake_case` JSON, ISO-8601 UTC timestamps, cursor-based pagination, error envelope `{error: {code, message, details}}`. OpenAPI auto-generated at `/docs`.

---

## 5. Technology Implementation Plan

**Backend skeleton:** FastAPI + SQLAlchemy 2.0 (async) + `asyncpg` + Pydantic v2.

```
api/
├── app/
│   ├── api/          # routers (auth, patients, doctors, scribe, chat)
│   ├── services/     # business logic
│   ├── ai/           # llm.py, embeddings.py, retrieval.py, chunking.py, deepgram.py
│   ├── db/           # models, session, RLS helpers, migrations
│   ├── workers/      # ingestion worker
│   └── core/         # config, auth, middleware, audit
```

**Transcription (Deepgram):** FastAPI proxies a WebSocket between the browser and Deepgram's streaming API (`nova-2-medical` + diarization). `asyncio.gather` runs two coroutines — client-to-Deepgram audio forwarding and Deepgram-to-client transcript streaming. On disconnect, the buffered transcript is persisted and the finalization job generates the SOAP + patient notes.

**LLM (Anthropic):** single `AnthropicClient` wrapper exposing:
- `summarize_consultation(transcript) -> (soap_note, patient_note)`
- `translate_document(text) -> translated_text`
- `chat(messages, context_chunks, scope) -> AsyncIterator[str]`

Use `claude-sonnet-4-5` for all three. Prompt caching on system prompts reduces cost on multi-turn chats. Streaming via `messages.stream()` relayed over SSE.

**Embeddings + vector search:** `voyage-3` (1024 dims) stored in `document_chunks.embedding`. HNSW index:
```sql
CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops);
```

---

## 6. Phased Delivery Plan

Phase 1 is a shared foundation all three engineers build together. After Phase 1 freezes the interfaces, Phases 2, 3, and 4 run in parallel on disjoint file sets.

### Phase 1 — Initial Setup (All: Vishal, Darsh, Ashutosh)

Foundation required by every downstream phase. No feature work begins until Phase 1 is merged to `main`.

| Area | Deliverable | Owner |
|---|---|---|
| Repo | Monorepo: `/web` (Next.js), `/api` (FastAPI), `/db` (migrations, seed) | Vishal |
| Env | `.env.example`, shared secrets convention (Anthropic, Deepgram, Voyage keys) | Vishal |
| DB | PostgreSQL + `pgvector` install script, base schema, RLS policies | Ashutosh |
| Auth | JWT issuance, refresh, httpOnly cookies, role middleware (`patient` / `doctor`) | Darsh |
| Shared AI primitives | `app/ai/llm.py`, `app/ai/embeddings.py`, `app/ai/retrieval.py`, `app/ai/chunking.py` | Ashutosh |
| UI shell | Next.js layout, login/register pages, role-based route guard, design tokens | Darsh |
| API contract | OpenAPI stubs for all endpoints in Sections 4 (empty handlers returning 501) | Vishal |

**Phase 1 exit criteria:**
- `docker`-free local dev: one command starts Postgres, one starts API, one starts web.
- A patient and a doctor account can log in, land on role-appropriate empty dashboards.
- RLS policies verified with a manual cross-account read test (must return zero rows).
- `AnthropicClient.chat("ping")` returns a response from within FastAPI.
- Shared interfaces below are frozen.

**Frozen interfaces (do not modify after Phase 1):**

```python
# app/ai/retrieval.py
async def retrieve(query: str, patient_ids: list[UUID], k: int = 8) -> list[Chunk]: ...

# app/ai/llm.py
class AnthropicClient:
    async def chat(self, messages, context_chunks, scope) -> AsyncIterator[str]: ...
    async def summarize_consultation(self, transcript: str) -> tuple[str, str]: ...
    async def translate_document(self, text: str) -> str: ...

# app/ai/embeddings.py
async def embed(texts: list[str]) -> list[list[float]]: ...

# app/ai/chunking.py
def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]: ...
```

---

### Phase 2 — Vishal: Doctor Module + Ambient Scribe

**Scope:** everything a doctor touches, including the live scribe pipeline.

**Backend (`/api`):**
- `app/api/doctors.py` — `/doctors/me/patients`, `/patients/{id}`, `/patients`, `/appointments/*`
- `app/api/scribe.py` — `WS /ws/scribe/{appointment_id}`, `POST /scribe/{id}/finalize`, `PATCH /clinical-notes/{id}`, `POST /clinical-notes/{id}/sign`
- `app/services/scribe_service.py` — transcript buffering, Deepgram proxy coroutine pair
- `app/services/doctor_service.py` — patient/appointment CRUD
- `app/ai/deepgram.py` — streaming client wrapper

**Frontend (`/web`):**
- `/app/doctor/dashboard` — patient list, search
- `/app/doctor/patients/[id]` — patient detail view (read-only tabs: overview, appointments, notes, documents)
- `/app/doctor/appointments` — calendar + CRUD
- `/app/doctor/scribe/[appointmentId]` — live scribe UI with `MediaRecorder`, WebSocket client, live transcript pane, SOAP + patient-note review/sign-off screen

**Dependencies from Phase 1:** auth, RLS, `AnthropicClient.summarize_consultation`.
**Does NOT touch:** patient-facing UI, chatbot endpoints, ingestion worker.

---

### Phase 3 — Darsh: Patient Module + Translator + Patient Chatbot

**Scope:** everything a patient sees, plus the patient-scoped chatbot endpoint.

**Backend (`/api`):**
- `app/api/patients.py` — `/patients/me`, `/patients/me/documents` (GET + POST multipart), `/patients/me/appointments`, `/patients/me/notes`
- `app/api/translate.py` — `POST /patients/me/documents/{id}/translate`
- `app/api/chat_patient.py` — `POST /chat/patient` (SSE)
- `app/services/patient_service.py` — patient view aggregation
- `app/services/translator_service.py` — PDF text extraction + Claude translation

**Frontend (`/web`):**
- `/app/patient/dashboard` — timeline of appointments, recent notes, documents
- `/app/patient/documents` — upload widget, document list, "Translate" action
- `/app/patient/documents/[id]` — side-by-side original vs. plain-English view with glossary
- `/app/patient/chat` — chat UI with SSE streaming, message history

**Dependencies from Phase 1:** auth, RLS, `AnthropicClient.chat`, `AnthropicClient.translate_document`, `retrieval.retrieve`.
**Does NOT touch:** doctor UI, scribe, ingestion worker, doctor chatbot.

**Write-side/read-side contract:** Darsh's upload endpoint writes a row to `documents` and sets `ingestion_status = 'pending'`. Ashutosh's worker picks it up. Darsh's chatbot calls `retrieval.retrieve(query, [current_patient_id])` — it does not care how chunks got there.

---

### Phase 4 — Ashutosh: Ingestion Worker + Doctor Chatbot + Audit/Guardrails

**Scope:** the data-plumbing backbone plus the doctor's cross-patient chatbot.

**Backend (`/api`):**
- `app/workers/ingestion_worker.py` — polls `documents` and `clinical_notes` for `ingestion_status = 'pending'`, chunks, embeds, writes to `document_chunks`, marks `ready`. Runs as a separate `python -m app.workers.ingestion_worker` process.
- `app/api/chat_doctor.py` — `POST /chat/doctor` (SSE), accepts optional `patient_id` filter inside the doctor's care team
- `app/services/guardrails.py` — prompt-injection scrub on retrieved chunks, system-prompt templates, refusal detection
- `app/core/audit.py` — middleware writing `audit_events` on clinical reads and all mutations
- `app/services/chat_service.py` — shared chat orchestration used by both `chat_patient.py` and `chat_doctor.py` (retrieval → guardrails → Claude stream)

**Frontend (`/web`):**
- `/app/doctor/chat` — doctor chatbot UI, optional patient filter dropdown, SSE streaming

**Dependencies from Phase 1:** auth, RLS, `retrieval.retrieve`, `embed`, `chunk_text`, `AnthropicClient.chat`.
**Does NOT touch:** scribe, patient UI, document upload UI.

**Contract tests Ashutosh owns:**
- Patient A cannot retrieve Patient B's chunks (expected: zero rows).
- Doctor outside Patient A's care team cannot retrieve Patient A's chunks.
- Prompt injection inside an uploaded document (e.g., "ignore previous instructions") does not alter Claude's scope.

---

### Integration Points & Shared Contracts

| Contract | Producer | Consumer |
|---|---|---|
| `documents` row with `ingestion_status='pending'` | Darsh (upload) | Ashutosh (worker) |
| `clinical_notes` row with `ingestion_status='pending'` | Vishal (scribe finalize) | Ashutosh (worker) |
| `document_chunks` rows with embeddings | Ashutosh (worker) | Darsh + Ashutosh (retrieval) |
| `retrieval.retrieve(q, patient_ids)` | Phase 1 (Ashutosh) | Darsh (patient chat), Ashutosh (doctor chat) |
| `AnthropicClient.chat()` | Phase 1 (Ashutosh) | Darsh, Ashutosh |
| `AnthropicClient.summarize_consultation()` | Phase 1 (Ashutosh) | Vishal |
| `AnthropicClient.translate_document()` | Phase 1 (Ashutosh) | Darsh |
| `get_current_user()` dependency | Phase 1 (Darsh) | All |

After Phase 1, these contracts are frozen. Any change requires a three-way sync.
