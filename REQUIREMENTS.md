# REQUIREMENTS.md

## My Interpretation of the Brief

This document is my restatement of the VentureDive take-home brief, resolved to the level of precision needed to build against it. Where the brief left room for interpretation I have made an explicit decision and noted it.

---

## Functional Requirements

### FR-1 — Article Ingestion
- The user submits a Wikipedia article URL via a web form.
- The backend fetches and parses the article HTML, extracting clean prose (title, section bodies). Infoboxes, navboxes, and reference list markup are discarded.
- The backend generates a concise summary of the article using the local LLM.
- The backend chunks the article text, generates embeddings for each chunk, and stores them in the vector database.
- The frontend displays the article title and summary once ingestion completes.
- Each new ingestion replaces the previous article entirely — there is no multi-article history.

### FR-2 — Conversational Chat
- Below the summary, a chat interface lets the user ask natural-language questions about the article.
- Every answer must be grounded in retrieved chunks from the vector database, not in the model's parametric knowledge.
- If the answer is not present in the article, the model must say so rather than hallucinate.
- The chat history persists for the session (in-browser); refreshing resets it.

### FR-3 — Error Handling
- Non-Wikipedia URLs are rejected with a clear user-facing message.
- URLs that resolve to a Wikipedia disambiguation page or produce no parseable text return an error rather than an empty summary.
- LLM or vector DB timeouts surface as error messages, not silent failures.

### FR-4 — Health Check
- A `GET /health` endpoint returns `{"status": "ok"}` so Docker health checks and compose depends-on work correctly.

---

## Non-Functional Requirements

### NFR-1 — Local-only inference
The running application must make zero calls to hosted LLM APIs (OpenAI, Anthropic, Gemini, Cohere, etc.). All inference runs through Ollama.

### NFR-2 — Single-command startup
`docker compose up` brings up the entire stack from a cold state. The first run pulls Ollama model weights; subsequent runs use the cached volume.

### NFR-3 — Test coverage
≥ 85% line coverage on application code. The entrypoint (`main.py`), `__init__.py` files, and Pydantic model definitions are excluded from the threshold calculation. Run `pytest --cov=app --cov-report=html` to generate the HTML report locally.

### NFR-4 — No secrets in the repository
All configuration that could be sensitive (base URLs, ports, model names) lives in environment variables documented in `.env.example`. No `.env` file is committed.

### NFR-5 — Response latency
Not a hard SLA, but the stack must produce a summary within a reasonable wall-clock time on a developer laptop (target: under 60 seconds running llama3.2:3b). This is a known constraint of local 3B CPU inference; the LLM timeout is set to 120 s to accommodate slower machines.

### NFR-6 — Disk footprint
Total model storage must stay under 2.5 GB. See model choices in DESIGN.md.

---

## In Scope

- Single Wikipedia article ingestion (one at a time, replace-on-new).
- Article summary generation via local LLM.
- Chunked embedding + vector storage via local embedding model + Qdrant.
- RAG-grounded chat (top-8 chunk retrieval, injected into prompt context).
- Single-page frontend (plain HTML/CSS/JS) served via NGINX.
- Full Docker Compose stack.
- ≥ 85% unit test coverage + one integration test.
- REQUIREMENTS.md, DESIGN.md, TASKS.md planning artefacts.
- README with run instructions.

## Out of Scope

- Authentication or user accounts.
- Multi-article history or persistent chat sessions across refreshes.
- Article re-ingestion diffing (changed content since last ingest).
- PDF, non-Wikipedia URL, or arbitrary web scraping support.
- Streaming LLM responses (nice to have; excluded to keep scope tight).
- Mobile-native app.
- CI/CD pipeline beyond what runs locally.
- Monitoring, logging infrastructure, or tracing beyond structured stderr logs.

---

## Assumptions Made

| # | Assumption | Reasoning |
|---|---|---|
| A1 | One article in memory at a time is acceptable UX | Brief states this explicitly. Drop-and-recreate on each `/ingest` is the simplest correct implementation. |
| A2 | Wikipedia articles in English only | Parsing and prompt engineering are tuned for English prose. Non-English articles may produce degraded results. |
| A3 | The developer machine can run a 3B-class model | Brief explicitly calls this out. `llama3.2:3b` chosen. If the machine cannot, the README documents the workaround. |
| A4 | Ollama is run inside Docker | The compose file includes an Ollama service. A `HOST_OLLAMA` env-var escape hatch is documented for machines where containerised GPU access is unavailable. |
| A5 | Chat context is browser-session-only | No server-side chat history. The frontend holds the message list; a page refresh clears it. |
| A6 | Wikipedia's public HTML structure is stable enough for targeted parsing | Wikipedia has used the same basic HTML structure since ~2010. The scraper targets `#mw-content-text p` tags within the main content div. If Wikipedia changes its structure this will break; noted as a known fragility. |
| A7 | Top-8 chunk retrieval is sufficient for a single article | A single Wikipedia article rarely exceeds 10,000 tokens. Eight 500-character chunks (4,000 chars of context) is a generous window relative to the article size. `all-minilm` produces lower cosine scores than larger models, so a score threshold of 0.1 is used instead of the typical 0.3. |

---

## Open Questions Resolved Unilaterally

**Q: Should summaries be cached between sessions?**
No. Re-ingesting the same URL re-generates the summary. The LLM call is fast enough at 3B scale that caching adds complexity without meaningful benefit.

**Q: How should disambiguation pages be handled?**
Detected by checking for the `dmbox-disambig` CSS class in the parsed `#mw-content-text` element. Return a 400 with a clear message.

**Q: Should the chat retain context across turns (multi-turn conversation)?**
The LLM prompt includes the last 3 exchanges as conversation history to give coherent follow-up handling, but the primary grounding is always the retrieved chunks — not accumulated model context. This keeps answers factual while avoiding context-window blowout on a 3B model.
