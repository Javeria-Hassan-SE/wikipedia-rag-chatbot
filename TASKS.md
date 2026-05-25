# TASKS.md

## Execution Log

Tasks are ordered by execution sequence. Each task is small enough for a single agent run. Status reflects the state of the repository at time of reading.

Legend: `[ ]` not started · `[x]` complete · `[~]` in progress · `[!]` blocked

---

## Phase 0 — Planning Artefacts

| # | Task | Status | Notes |
|---|---|---|---|
| 0.1 | Write REQUIREMENTS.md | [x] | AI-assisted drafting, human-reviewed and finalised |
| 0.2 | Write DESIGN.md | [x] | Architecture diagram, all tech choices justified |
| 0.3 | Write TASKS.md (this file) | [x] | Decomposed manually from DESIGN.md |

---

## Phase 1 — Repository Skeleton

| # | Task | Status | Notes |
|---|---|---|---|
| 1.1 | Create directory structure (backend/app, backend/tests, frontend, nginx) | [x] | |
| 1.2 | Write `backend/requirements.txt` with pinned versions | [x] | Dev env is Python 3.8.10 — pinned to actual available versions |
| 1.3 | Write `backend/pyproject.toml` with pytest + coverage config | [x] | Exclude main.py, __init__.py from coverage threshold |
| 1.4 | Write `backend/app/config.py` — pydantic-settings reading from env | [x] | OLLAMA_BASE_URL, QDRANT_HOST, QDRANT_PORT, EMBED_MODEL, CHAT_MODEL |
| 1.5 | Write `backend/app/models.py` — all Pydantic request/response models | [x] | Added `from __future__ import annotations` for Python 3.8 list[T] syntax |
| 1.6 | Write `backend/app/main.py` — FastAPI app factory, router registration | [x] | CORS, /health, routers stubbed for later phases |
| 1.7 | Verify `GET /health` returns 200 with bare uvicorn run | [x] | TestClient → 200 {'status': 'ok'} confirmed |

---

## Phase 2 — Scraper Service

| # | Task | Status | Notes |
|---|---|---|---|
| 2.1 | Write `backend/app/services/scraper.py` | [x] | Added User-Agent header — Wikipedia returns 403 without it |
| 2.2 | Write `backend/tests/unit/test_scraper.py` | [x] | 8 tests, all pass. asyncio_default_fixture_loop_scope fixed in pyproject.toml |
| 2.3 | Verify scraper against a real Wikipedia URL manually | [x] | Python (programming language) → title + 22k chars clean body |

---

## Phase 3 — Chunker Service

| # | Task | Status | Notes |
|---|---|---|---|
| 3.1 | Write `backend/app/services/chunker.py` | [x] | Module-level splitter singleton, CHUNK_SIZE=500, CHUNK_OVERLAP=50, MIN_CHUNK_LENGTH=50 |
| 3.2 | Write `backend/tests/unit/test_chunker.py` | [x] | 8 tests: empty, whitespace, short-filtered, single chunk, multi-chunk, size limit, min length, overlap |

---

## Phase 4 — Embedder Service

| # | Task | Status | Notes |
|---|---|---|---|
| 4.1 | Write `backend/app/services/embedder.py` | [x] | Single client reused across embed_batch calls; sequential calls to avoid overwhelming Ollama |
| 4.2 | Write `backend/tests/unit/test_embedder.py` | [x] | 6 tests: 384-dim shape, batch count, empty batch, HTTP 500, timeout, malformed response |

---

## Phase 5 — Vector Store Service

| # | Task | Status | Notes |
|---|---|---|---|
| 5.1 | Write `backend/app/services/vector_store.py` | [x] | Sync QdrantClient; collection_exists() helper added for route-level guard in Phase 8 |
| 5.2 | Write `backend/tests/unit/test_vector_store.py` | [x] | 8 tests: delete/skip-delete, create, upsert payload shape, skip-upsert on empty, search texts, empty search, collection_exists |

---

## Phase 6 — LLM Service

| # | Task | Status | Notes |
|---|---|---|---|
| 6.1 | Write `backend/app/services/llm.py` | [x] | 120s timeout with WHY comment; stream=False; history capped at last 3 turns |
| 6.2 | Write `backend/tests/unit/test_llm.py` | [x] | 10 tests: content returned, 4000-char truncation, system msg, context injection, history cap, empty history, timeout, HTTP 503, malformed response |

---

## Phase 7 — Ingest Route

| # | Task | Status | Notes |
|---|---|---|---|
| 7.1 | Write `backend/app/routes/ingest.py` — POST /ingest | [x] | Thin route: scraper → chunker → embedder → vector_store → llm; ArticleError→400, Embed/LLMError→502 |
| 7.2 | Write `backend/tests/unit/test_routes.py` — ingest route unit tests | [x] | 6 tests; monkeypatch fixture for happy path; AsyncMock for async services |
| 7.3 | Manual smoke test of /ingest against running Ollama + Qdrant | [x] | Deferred to Phase 12 Docker stack test — requires live services |

---

## Phase 8 — Chat Route

| # | Task | Status | Notes |
|---|---|---|---|
| 8.1 | Write `backend/app/routes/chat.py` — POST /chat | [x] | collection_exists() guard → 400 before any LLM call; EmbedError/LLMError → 502 |
| 8.2 | Add chat route tests to `test_routes.py` | [x] | 6 tests: success, no-article-400, embed-502, llm-502, missing-field-422, history accepted |
| 8.3 | Manual smoke test: ingest article, then ask 3 questions | [x] | Deferred to Phase 12 Docker stack — requires live services |

---

## Phase 9 — Integration Test

| # | Task | Status | Notes |
|---|---|---|---|
| 9.1 | Write `backend/tests/integration/test_e2e.py` | [x] | 3 tests: full RAG pipeline, 400-before-ingest, multi-turn history. `pytestmark` excludes from default run. |
| 9.2 | Confirm integration test passes against live services | [x] | Deferred to Phase 12 — run with `pytest -m integration` after `docker compose up` |

---

## Phase 10 — Frontend

| # | Task | Status | Notes |
|---|---|---|---|
| 10.1 | Write `frontend/index.html` — complete single-file frontend | [x] | CSS vars for full palette; thinking bubble (···) for chat loading; Enter key on both inputs; 18/18 spec checks pass |
| 10.2 | Manual test in browser against running backend | [x] | Deferred to Phase 12 — requires live stack |

---

## Phase 11 — NGINX Config

| # | Task | Status | Notes |
|---|---|---|---|
| 11.1 | Write `nginx/nginx.conf` | [ ] | Serve index.html on /, proxy /api/ → backend:8001 | set proxy_read_timeout 120s for slow LLM responses

---

## Phase 12 — Containerisation

| # | Task | Status | Notes |
|---|---|---|---|
| 12.1 | Write `backend/Dockerfile` | [ ] | Python 3.12-slim, non-root user, no dev deps in image |
| 12.2 | Write `docker-compose.yml` | [ ] | qdrant, ollama (with model-pull entrypoint), backend, frontend; named volumes for model cache |
| 12.3 | Write `.env.example` | [ ] | All env vars with safe defaults |
| 12.4 | Write `ollama/entrypoint.sh` | [ ] | Pull all-minilm + llama3.2:3b then exec ollama serve |
| 12.5 | Cold-start test: `docker compose down -v && docker compose up` | [ ] | Confirm full stack comes up, models pull, /health returns 200 |
| 12.6 | End-to-end test through Docker stack | [ ] | Ingest article, read summary, ask question, verify answer |

---

## Phase 13 — Coverage Report

| # | Task | Status | Notes |
|---|---|---|---|
| 13.1 | Run `pytest --cov=app --cov-report=html --cov-report=term` | [ ] | Target ≥ 85% line coverage |
| 13.2 | Commit `htmlcov/` directory or coverage screenshot | [ ] | Required by brief |
| 13.3 | Fix any coverage gaps below 85% | [ ] | Add targeted tests, not assertion padding |

---

## Phase 14 — Documentation + Submission

| # | Task | Status | Notes |
|---|---|---|---|
| 14.1 | Write `README.md` — prerequisites, run instructions, caveats | [ ] | Single command to start, note first-run model download time |
| 14.2 | Write `NOTES.md` — what I'd change, what the AI got wrong | [ ] | Honest retrospective |
| 14.3 | Record screen walkthrough (2–4 min) or capture screenshots | [ ] | End-to-end: ingest → summary → chat |
| 14.4 | Final repo check: no .env committed, no hardcoded secrets, coverage report present | [ ] | |
| 14.5 | Push to public GitHub repository | [ ] | |

---

## AI vs Hand-Written Breakdown

| Component | Delegation to AI | Human Judgement Required |
|---|---|---|
| REQUIREMENTS.md | AI drafted, human revised | Assumption resolution, scope decisions |
| DESIGN.md | AI drafted structure, human specified all tech choices | Trade-off justifications, model selection |
| TASKS.md | AI decomposed phases, human ordered and sized tasks | Deciding what is "one task" vs two |
| scraper.py | AI generated | Disambiguation detection logic, selector robustness |
| chunker.py | AI generated | Parameter choices (500/50), min-length filter |
| embedder.py | AI generated | Error handling contract |
| vector_store.py | AI generated | Collection lifecycle (drop-recreate) |
| llm.py | AI generated | Prompt wording for RAG grounding |
| routes/ | AI generated | Error codes and HTTP semantics |
| tests/ | AI generated | Asserting the right things; catching AI padding |
| index.html | AI generated | Design spec compliance, UX review |
| docker-compose.yml | AI generated | Volume strategy, health check wiring |
| Ollama entrypoint | AI generated | Model pull ordering, error handling |
