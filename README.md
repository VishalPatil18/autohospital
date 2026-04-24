# Decode — AI-Powered Medical Platform

Next.js 14 frontend + FastAPI backend + PostgreSQL + pgvector.

---

## Phase 1 Setup

### Prerequisites

- Python 3.11+ and `uv`
- Node.js 18+ and `pnpm`
- PostgreSQL 15+ with `pgvector` extension

### 1. Database

```bash
# Run once to create the DB and extensions
psql -U postgres -f db/setup.sql

# Seed test users (password: password123 for all accounts)
psql -U postgres -d decode -f db/seed.sql
```

### 2. API (FastAPI)

```bash
cd api
cp ../.env.example .env
# Edit .env — fill in ANTHROPIC_API_KEY, VOYAGE_API_KEY, DEEPGRAM_API_KEY

uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
# → http://localhost:8000/docs
```

### 3. Web (Next.js)

```bash
cd web
cp .env.local.example .env.local

pnpm install
pnpm dev
# → http://localhost:3000
```

### Phase 1 Exit Checklist

- [ ] `pnpm dev` serves login page at http://localhost:3000
- [ ] `uvicorn app.main:app --reload` serves `/docs` at http://localhost:8000
- [ ] Patient login (alice@example.com / password123) lands on `/patient/dashboard`
- [ ] Doctor login (drsmith@example.com / password123) lands on `/doctor/dashboard`
- [ ] `SELECT * FROM documents` as patient A returns only A's rows (RLS verified)
- [ ] `python -c "from app.ai.llm import AnthropicClient; import asyncio; c=AnthropicClient(); print(asyncio.run(c.translate_document('test')))"` round-trips to Claude
- [ ] `python -c "from app.ai.retrieval import retrieve; import asyncio; print(asyncio.run(retrieve('test', [])))"` returns `[]` without error

### Seed Accounts

| Email | Password | Role |
|---|---|---|
| alice@example.com | password123 | patient |
| bob@example.com | password123 | patient |
| drsmith@example.com | password123 | doctor |
| drjones@example.com | password123 | doctor |

Dr. Smith is in Alice's care team. Dr. Jones has no care team assignment yet.

---

## Repo Layout

```
decode/
├── web/                      # Next.js 14 (App Router)
│   ├── app/
│   │   ├── (auth)/login, register
│   │   ├── patient/dashboard
│   │   └── doctor/dashboard
│   ├── components/           # auth-provider, nav
│   ├── lib/                  # api.ts, auth.ts
│   └── middleware.ts         # route protection + role guards
├── api/                      # FastAPI
│   ├── app/
│   │   ├── api/              # auth, patients, doctors, scribe, chat_*, translate
│   │   ├── ai/               # llm.py, embeddings.py, chunking.py, retrieval.py
│   │   ├── db/               # models, session, rls, schemas
│   │   ├── core/             # config, auth middleware
│   │   ├── services/         # (Phase 2/3/4)
│   │   └── workers/          # ingestion worker (Phase 4)
│   ├── alembic/              # migrations
│   └── pyproject.toml
├── db/
│   ├── setup.sql             # DB + extension creation
│   └── seed.sql              # test data
├── .env.example
└── docs/
    ├── plan.md               # execution plan
    └── srs.md                # requirements spec
```

## Frozen Interfaces (do not modify after Phase 1)

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

See `docs/plan.md` for branch strategy and Phase 2/3/4 ownership.
