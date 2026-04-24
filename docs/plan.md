# Decode — Vibe-Coding Execution Plan

Companion to `srs.md`. This file is the "how we actually ship it" plan: branching, ownership, task order, prompts to feed Cursor / Claude Code, and daily sync points.

---

## 0. Ground Rules

- **Branch strategy:** `main` is protected. Four long-lived branches: `phase-1-setup`, `phase-2-vishal`, `phase-3-darsh`, `phase-4-ashutosh`. PR into `main` only after phase owner self-reviews.
- **Phase 1 is a blocker.** Nobody starts Phase 2/3/4 until Phase 1 is merged and the frozen interfaces in `srs.md` §6 are deployed.
- **Freeze rule:** after Phase 1, shared files in `app/ai/`, `app/core/auth.py`, `db/migrations/` are read-only for Phase 2/3/4 owners. Need a change? Post in the team chat, get both other owners to ack, then edit on a short-lived branch that all three rebase onto.
- **Contract over implementation.** Stub what you need from another phase with a fake that returns realistic data; swap in the real call at integration time.
- **Test the seams, not the internals.** One integration test per contract boundary (see §6).

---

## 1. Repo Layout

```
decode/
├── web/                      # Next.js 14 (App Router)
│   ├── app/
│   │   ├── (auth)/login, register
│   │   ├── patient/          # Darsh
│   │   └── doctor/           # Vishal (CRM, scribe), Ashutosh (chat)
│   ├── components/
│   ├── lib/
│   └── package.json
├── api/                      # FastAPI
│   ├── app/
│   │   ├── api/              # routers
│   │   ├── services/
│   │   ├── ai/               # frozen after Phase 1
│   │   ├── db/
│   │   ├── workers/          # Ashutosh
│   │   └── core/
│   ├── tests/
│   └── pyproject.toml
├── db/
│   ├── migrations/           # alembic
│   └── seed.sql
├── .env.example
└── README.md
```

---

## 2. Phase 1 — Initial Setup (Day 0, all three)

Timebox: 4–6 hours, done together on one call.

### Task list (in order)

1. **Vishal** — scaffold `web/` with `pnpm create next-app@latest` (TypeScript, App Router, Tailwind), scaffold `api/` with `uv init` or `poetry new`, commit `.env.example`.
2. **Ashutosh** — install Postgres locally, enable `pgvector` (`CREATE EXTENSION vector;`), write the base Alembic migration covering:
   - `users(id, email, password_hash, role, created_at)`
   - `patients(user_id, dob, ...)`
   - `doctors(user_id, specialty, ...)`
   - `care_team(doctor_id, patient_id)`
   - `appointments(id, patient_id, doctor_id, scheduled_at, status)`
   - `documents(id, patient_id, filename, storage_path, ingestion_status, uploaded_at)`
   - `clinical_notes(id, appointment_id, soap_text, signed_at, ingestion_status)`
   - `patient_notes(id, appointment_id, plain_text)`
   - `transcripts(id, appointment_id, content, created_at)`
   - `document_chunks(id, patient_id, source_type, source_id, chunk_text, embedding vector(1024))`
   - `chat_messages(id, user_id, conversation_id, role, content, created_at)`
   - `audit_events(id, actor_id, action, resource_type, resource_id, ip, created_at)`
3. **Ashutosh** — write RLS policies (see `srs.md` §3) and a helper `with_user_context(session, user_id, role)` that issues `SET LOCAL` before queries.
4. **Darsh** — implement `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, the `get_current_user()` FastAPI dependency, httpOnly cookie handling, and a Next.js auth provider (`useAuth()` hook).
5. **Darsh** — build the Next.js shell: root layout, shared nav, `/login`, `/register`, role-based redirect (`patient` → `/patient/dashboard`, `doctor` → `/doctor/dashboard`), empty dashboard placeholders.
6. **Ashutosh** — implement the frozen AI primitives as working (not stub) code:
   - `app/ai/llm.py` — `AnthropicClient` with `chat`, `summarize_consultation`, `translate_document`.
   - `app/ai/embeddings.py` — `embed(texts)` calling Voyage.
   - `app/ai/chunking.py` — token-aware chunker.
   - `app/ai/retrieval.py` — `retrieve(query, patient_ids, k)` doing embed + pgvector query.
7. **Vishal** — add OpenAPI stub routers: every endpoint from `srs.md` §4 exists and returns 501, typed with Pydantic request/response models. This is the contract the frontend can code against from day one.
8. **Seed script** — two patients, two doctors, one care-team mapping, a sample appointment. Commit as `db/seed.sql`.

### Exit checklist (all must pass)

- [ ] `pnpm dev` in `web/` serves login page.
- [ ] `uvicorn app.main:app --reload` in `api/` serves `/docs`.
- [ ] Patient login lands on `/patient/dashboard`, doctor login lands on `/doctor/dashboard`.
- [ ] `SELECT * FROM documents` as patient A returns only A's rows (verified with psql + `SET app.current_user_id`).
- [ ] `python -c "from app.ai.llm import AnthropicClient; ..."` round-trips to Claude.
- [ ] `retrieval.retrieve("test", [patient_a_id])` returns `[]` without error on an empty table.

---

## 3. Phase 2 — Vishal (Doctor + Ambient Scribe)

### Build order

1. **Doctor dashboard backend** — `GET /doctors/me/patients`, `GET /patients/{id}`, patient/appointment CRUD. Wire to seed data.
2. **Doctor dashboard frontend** — patient list page, patient detail tabs (overview, appointments, notes, documents — notes/documents tabs can be empty panes for now; they fill in once Darsh and Ashutosh land).
3. **Appointment calendar** — simple list or week-grid, CRUD modal.
4. **Scribe WebSocket plumbing** — `WS /ws/scribe/{appointment_id}` accepts audio frames, forwards to Deepgram, streams transcript back. Persist on disconnect.
5. **Scribe UI** — `MediaRecorder` → WebSocket, live diarized transcript pane, Start/Stop/End buttons.
6. **Finalization** — `POST /scribe/{id}/finalize` calls `AnthropicClient.summarize_consultation(transcript)`, writes `clinical_notes` + `patient_notes`, sets `clinical_notes.ingestion_status='pending'` (so Ashutosh's worker picks it up for RAG).
7. **Review & sign-off screen** — editable SOAP, editable plain-English notes, Sign button → `POST /clinical-notes/{id}/sign` (sets `signed_at`, locks the row).

### Files Vishal owns

```
api/app/api/doctors.py
api/app/api/scribe.py
api/app/services/doctor_service.py
api/app/services/scribe_service.py
api/app/ai/deepgram.py
web/app/doctor/dashboard/
web/app/doctor/patients/[id]/
web/app/doctor/appointments/
web/app/doctor/scribe/[appointmentId]/
```

### Cursor / Claude Code prompts

> **Scribe WebSocket handler**
> "In `api/app/api/scribe.py`, implement a FastAPI WebSocket endpoint at `/ws/scribe/{appointment_id}`. Use `asyncio.gather` to run two coroutines: one reads audio bytes from the client WebSocket and forwards them to a Deepgram streaming connection (from `app/ai/deepgram.py`); the other reads transcript events from Deepgram and sends JSON `{type, text, is_final, speaker}` messages back to the client. Buffer all final transcript segments in memory keyed by appointment_id. On client disconnect, persist the buffered transcript to the `transcripts` table using the existing async session and `with_user_context`."

> **Finalization endpoint**
> "Add `POST /scribe/{appointment_id}/finalize` that loads the transcript for the appointment, calls `AnthropicClient.summarize_consultation(transcript)` to get `(soap, patient_friendly)`, writes both to `clinical_notes` and `patient_notes`, and sets `clinical_notes.ingestion_status='pending'`. Return both artifacts in the response so the UI can show them immediately."

### Stubs Vishal needs (replaced by real impls at integration)

- None beyond Phase 1. `AnthropicClient.summarize_consultation` is real from day one.

---

## 4. Phase 3 — Darsh (Patient + Translator + Patient Chatbot)

### Build order

1. **Patient dashboard backend** — `GET /patients/me`, `GET /patients/me/appointments`, `GET /patients/me/notes`, `GET /patients/me/documents`.
2. **Patient dashboard frontend** — timeline view combining recent appointments and notes, document list.
3. **Document upload** — `POST /patients/me/documents` (multipart, stored on local disk under `storage/documents/{patient_id}/{doc_id}.pdf`), row written with `ingestion_status='pending'`. Upload widget with progress.
4. **Translator** — `POST /patients/me/documents/{id}/translate`: extract PDF text with `pypdf`, pass to `AnthropicClient.translate_document`, cache result in a `document_translations` column or table. Side-by-side UI.
5. **Patient chatbot endpoint** — `POST /chat/patient`: read user message, call `retrieval.retrieve(query, [current_patient_id])`, call `AnthropicClient.chat(messages, chunks, scope='patient')`, return `StreamingResponse` (SSE).
6. **Chat UI** — simple message list + composer, EventSource for SSE, per-token rendering, conversation history persisted to `chat_messages`.

### Files Darsh owns

```
api/app/api/patients.py
api/app/api/translate.py
api/app/api/chat_patient.py
api/app/services/patient_service.py
api/app/services/translator_service.py
web/app/patient/dashboard/
web/app/patient/documents/
web/app/patient/documents/[id]/
web/app/patient/chat/
```

### Cursor / Claude Code prompts

> **Upload endpoint**
> "Implement `POST /patients/me/documents` in `api/app/api/patients.py`. Accept a `multipart/form-data` PDF upload, validate MIME type, save to `storage/documents/{patient_id}/{doc_id}.pdf`, insert a `documents` row with `ingestion_status='pending'`, and return the document metadata. Enforce that `patient_id` comes from the JWT, never the request body."

> **Patient chat SSE**
> "Implement `POST /chat/patient` as an SSE endpoint. Body: `{message: str, conversation_id: str | None}`. Load prior messages for the conversation, call `retrieval.retrieve(message, [current_user_id])`, then iterate over `AnthropicClient.chat(messages, chunks, scope='patient')` and yield each token as `data: {json}\n\n`. Persist the user message and assistant reply to `chat_messages` at the start and end of the stream."

### Stubs Darsh needs

- During Phase 3, chunks may not exist yet (Ashutosh's worker lands in Phase 4). To unblock chat UI work, seed 5–10 fake chunks manually in `db/seed.sql` for one test patient. Remove once worker is live.

---

## 5. Phase 4 — Ashutosh (Ingestion + Doctor Chat + Guardrails + Audit)

### Build order

1. **Ingestion worker** — `python -m app.workers.ingestion_worker`. Loop: select up to N rows from `documents` and `clinical_notes` where `ingestion_status='pending'`, extract text, chunk via `chunking.chunk_text`, embed via `embeddings.embed`, insert into `document_chunks`, mark `ready`. Sleep 2 s. Handle failures with `ingestion_status='failed'` + retry count.
2. **Shared chat service** — `app/services/chat_service.py` with `async def run_chat(user_id, role, message, patient_filter) -> AsyncIterator[str]` that does retrieval + guardrails + Claude stream. Refactor Darsh's `/chat/patient` to call this (one-line change, coordinate the PR).
3. **Doctor chat endpoint** — `POST /chat/doctor` using the shared service. Resolves `patient_filter` from the doctor's `care_team`. Optional `?patient_id=` narrows to one patient.
4. **Doctor chat UI** — chat panel at `/doctor/chat`, patient filter dropdown populated from `/doctors/me/patients`.
5. **Guardrails** — `app/services/guardrails.py`:
   - Strip instruction-like patterns from retrieved chunks before assembly.
   - System-prompt template enforcing scope and refusal for off-scope queries.
   - Unit tests with injection strings.
6. **Audit middleware** — FastAPI middleware in `app/core/audit.py` logging every request touching clinical resources. Scope: `clinical_notes`, `patient_notes`, `documents`, `transcripts`, `chat_messages`.

### Files Ashutosh owns

```
api/app/workers/ingestion_worker.py
api/app/api/chat_doctor.py
api/app/services/chat_service.py
api/app/services/guardrails.py
api/app/core/audit.py
web/app/doctor/chat/
```

### Cursor / Claude Code prompts

> **Ingestion worker**
> "Write `api/app/workers/ingestion_worker.py` as a standalone async script. In a loop, open a DB session, select up to 20 rows from `documents` where `ingestion_status='pending'`, and for each: load the file from `storage_path`, extract text (PDF via pypdf, else read as UTF-8), call `chunking.chunk_text(text)`, call `embeddings.embed(chunks)`, bulk-insert into `document_chunks` with `patient_id`, `source_type='document'`, `source_id=doc.id`. Mark the document `ready`. Then do the same for `clinical_notes` with `source_type='clinical_note'`. Sleep 2 seconds between cycles. Log every state transition. On exception, mark the row `failed` and continue."

> **Shared chat service with guardrails**
> "Write `api/app/services/chat_service.py` with `run_chat(user_id, role, message, patient_ids, conversation_id)`. It should: embed the message, call `retrieval.retrieve(message, patient_ids)`, pass chunks through `guardrails.sanitize_chunks()`, build the Claude messages list with a role-specific system prompt from `guardrails.system_prompt(role, patient_ids)`, then `yield` tokens from `AnthropicClient.chat(...)`. Persist user and assistant messages to `chat_messages`."

### Contract tests Ashutosh owns

```python
# tests/test_cross_patient_isolation.py
async def test_patient_cannot_retrieve_other_patient_chunks(): ...
async def test_doctor_outside_care_team_cannot_retrieve(): ...
async def test_prompt_injection_in_document_does_not_change_scope(): ...
```

---

## 6. Integration Day (Day before demo)

One-hour sync, all three on a call, merge order:

1. Phase 2 → `main`
2. Phase 3 → `main`
3. Phase 4 → `main` (resolves conflicts if any in shared `chat_service` — unlikely if Phase 3 left the patient chat as a thin wrapper).
4. Run the integration smoke test:
   - Doctor creates a patient, schedules an appointment.
   - Doctor launches scribe, speaks for 2 minutes, stops.
   - Finalize → notes appear, `clinical_notes.ingestion_status='pending'`.
   - Wait 5 s → worker ingests → `document_chunks` has new rows.
   - Patient logs in, sees the plain-English note, opens chat, asks "what did the doctor say about my blood pressure?" → grounded answer.
   - Doctor opens their chat, asks the same thing scoped to that patient → grounded answer.
   - Doctor tries to query a patient not in their care team → refused.

---

## 7. Demo Script (5 minutes)

1. **Problem** (20 s) — patients don't understand reports; doctors spend hours on notes.
2. **Patient flow** (90 s) — upload a lab report, hit Translate, show plain-English view; open chatbot, ask a question about it.
3. **Doctor flow** (120 s) — open patient detail, launch scribe, role-play a 45-second consultation, stop, show generated SOAP note and patient-friendly note side by side, sign.
4. **Guardrail flourish** (30 s) — doctor chat refuses a query about a patient not in care team; patient chat refuses to speculate on a diagnosis.
5. **Architecture slide** (30 s) — the diagram from `srs.md` §1, call out that RLS is the security floor.
6. **Close** (10 s) — stack, team, thanks.

---

## 8. Risk & Mitigation

| Risk | Mitigation |
|---|---|
| Deepgram API flakiness on demo wifi | Pre-record a 45-second audio clip; have a "upload audio" fallback button in scribe UI that skips the WebSocket and sends the file to a batch transcribe endpoint. |
| Ingestion worker not running at demo time | Make it a systemd service + add a manual "Re-index" button in a hidden admin page. |
| RLS policy bug | Run Ashutosh's cross-patient test before every merge to `main`. |
| Claude rate limit mid-demo | Cache the demo's scribe output locally; if finalize fails, serve the cached SOAP note. |
| PDF extraction fails on scanned docs | Scope: only digital-text PDFs. Reject scanned PDFs with a clear error message. |

---

## 9. What's Explicitly Out of Scope

- Mobile app.
- E-prescribing, billing, insurance.
- Multi-tenant / multi-clinic isolation.
- HIPAA compliance certification (security model is HIPAA-shaped, not certified).
- Offline mode.
- Real-time collaboration on notes.
