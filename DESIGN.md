# DESIGN.md

## Architecture Overview

A four-service Docker Compose stack. The frontend is a static single-file HTML/JS application served by NGINX. All user actions hit the FastAPI backend, which orchestrates scraping, chunking, embedding, vector storage, and LLM calls. Qdrant and Ollama run as peer services.

---

## System Diagram

```
Browser
  │
  │  HTTP (port 80)
  ▼
┌─────────────────────────────────┐
│           NGINX                 │
│  - serves frontend/index.html   │
│  - /api/* → proxy backend:8001  │
└─────────────┬───────────────────┘
              │ HTTP (port 8001)
              ▼
┌─────────────────────────────────┐
│         FastAPI Backend         │
│                                 │
│  POST /ingest                   │
│    scraper ──► chunker          │
│      ──► embedder ──► qdrant    │
│      ──► llm (summarise)        │
│                                 │
│  POST /chat                     │
│    embedder (question)          │
│      ──► qdrant (top-5 search)  │
│      ──► llm (RAG answer)       │
│                                 │
│  GET /health                    │
└───────┬─────────────┬───────────┘
        │             │
        │ HTTP :6333  │ HTTP :11434
        ▼             ▼
┌──────────────┐  ┌──────────────┐
│    Qdrant    │  │    Ollama    │
│  vector DB   │  │  LLM runtime │
│              │  │  llama3.2:3b │
│  collection: │  │  all-minilm  │
│  "article"   │  │              │
└──────────────┘  └──────────────┘
```

---

## Components

### 1. NGINX (Frontend Server)
- Serves `frontend/index.html` as a static file.
- Proxies `/api/*` to the backend container to avoid CORS preflight overhead and avoids exposing the backend port directly to the browser.
- No TLS in development; `.env` documents how to add it for production.

### 2. FastAPI Backend
Organised into routes and services. Routes are thin — they validate input/output shapes and delegate to services. Services have no knowledge of HTTP.

```
app/
├── main.py              # app factory, router registration, CORS
├── config.py            # settings via pydantic-settings + env vars
├── models.py            # request/response Pydantic models
├── routes/
│   ├── ingest.py        # POST /ingest
│   └── chat.py          # POST /chat
└── services/
    ├── scraper.py        # fetch + parse Wikipedia HTML
    ├── chunker.py        # split text into chunks
    ├── embedder.py       # call Ollama /api/embeddings
    ├── vector_store.py   # Qdrant collection CRUD + search
    └── llm.py            # Ollama /api/chat (summarise + RAG answer)
```

Each service module exposes a small set of pure functions. No global state. Dependencies are injected via FastAPI's `Depends` mechanism where shared clients are needed (Qdrant client, httpx client).

### 3. Qdrant
- Runs as a Docker service on port 6333.
- Single collection: `article`, recreated on each `/ingest` call.
- Vector dimension: 384 (matches `all-minilm`).
- Distance metric: Cosine.
- Named Docker volume `qdrant_storage` persists data across restarts, though in practice a new ingest replaces it anyway.

### 4. Ollama
- Runs as a Docker service on port 11434.
- Two models:
  - `all-minilm` — embedding only (22 MB). Produces 384-dimension vectors.
  - `llama3.2:3b` — chat + summarisation (~2.0 GB).
- Models are pulled on first container start via an entrypoint script. A named volume `ollama_models` ensures they are not re-downloaded on subsequent starts.
- `OLLAMA_BASE_URL` env var allows pointing the backend at a host-side Ollama instead (useful if the host has a GPU and the container cannot access it).

**Why Qdrant over Chroma:**
Qdrant's Docker image (~200 MB) is significantly lighter than Chroma's Python-based server. Its REST client has stable semantics and is easier to mock cleanly in tests. Collection-level drop and recreate is a first-class operation, which maps directly to our "one article at a time" requirement. Chroma's embedded mode is unsuitable for a containerised service, and its server mode offers no advantages for this use case.

**Why `all-minilm` over `nomic-embed-text`:**
`nomic-embed-text` produces 768-dimension vectors and weighs 274 MB. `all-minilm` produces 384-dimension vectors at 22 MB. For a single Wikipedia article (at most a few hundred chunks), 384 dimensions provides more than enough semantic resolution. The 252 MB saving keeps total model storage under 2.5 GB (target from NFR-6).

---

## Data Flow — Ingestion

```
POST /ingest { url }
      │
      ▼
scraper.fetch_article(url)
  - httpx GET with 30s timeout
  - BeautifulSoup parse #mw-content-text
  - extract title from <h1 id="firstHeading">
  - extract paragraphs from <p> tags within section divs
  - strip citation superscripts [1], [2] etc.
  - detect disambiguation page → raise ArticleError
  → ArticleContent(title, body_text)
      │
      ▼
chunker.split(body_text)
  - RecursiveCharacterTextSplitter
  - chunk_size=500, chunk_overlap=50, length_function=len
  - minimum chunk length filter (drop chunks < 50 chars)
  → List[str]  (typically 20–150 chunks per article)
      │
      ▼
embedder.embed_batch(chunks)
  - POST ollama /api/embeddings { model: "all-minilm", prompt: chunk }
  - batched sequentially (Ollama does not expose batch embed)
  → List[List[float]]  (384-dim each)
      │
      ▼
vector_store.recreate_and_insert(chunks, embeddings)
  - delete collection "article" if exists
  - create collection "article" (size=384, distance=Cosine)
  - upsert points: id=index, vector=embedding, payload={text: chunk}
      │
      ▼
llm.summarise(body_text[:4000])
  - system: "You are a summarisation assistant. Produce a 3–5 sentence
    summary of the provided article text. Be factual and concise."
  - user: body_text[:4000]  (first 4000 chars is enough for a summary)
  → str
      │
      ▼
response { title, summary }
```

## Data Flow — Chat

```
POST /chat { question, history: [{role, content}] }
      │
      ▼
embedder.embed_single(question)
  → List[float]  (384-dim)
      │
      ▼
vector_store.search(query_vector, top_k=8)
  - Qdrant query_points, score_threshold=0.1
  → List[str]  (chunk texts, ranked by cosine similarity)
      │
      ▼
llm.answer(question, chunks, history[-3:])
  - system: "Answer using ONLY the provided context. If the answer is
    not in the context, say you don't know."
  - context block: joined chunk texts
  - conversation history: last 3 turns
  - user: question
  → str
      │
      ▼
response { answer }
```

---

## Chunking Strategy

| Parameter | Value | Reasoning |
|---|---|---|
| chunk_size | 500 chars | Fits comfortably in the context window injected into the RAG prompt (5 chunks × 500 = 2,500 chars). Wikipedia paragraphs average ~300–600 chars so most chunks are natural paragraph boundaries. |
| chunk_overlap | 50 chars | Prevents answers that straddle a chunk boundary from being missed. Small enough not to inflate the chunk count significantly. |
| splitter | RecursiveCharacterTextSplitter | Respects paragraph → sentence → word boundaries in order, minimising mid-sentence splits. |
| min chunk filter | 50 chars | Drops stray header residue and short transitional sentences that add noise without retrieval value. |

---

## RAG Prompt Design

The system prompt explicitly grounds the model:

```
You are a helpful assistant answering questions about a Wikipedia article.
Answer using ONLY the information in the context provided below.
If the answer cannot be found in the context, respond with:
"I don't have enough information in the article to answer that."
Do not use your general knowledge.

Context:
{chunk_1}

{chunk_2}

...
```

The model is `llama3.2:3b`. At this scale, keeping the prompt strict and short outperforms elaborate chain-of-thought instructions.

---

## API Contracts

### POST /ingest
```
Request:  { "url": "https://en.wikipedia.org/wiki/..." }
Response: { "title": "Article Title", "summary": "..." }
Errors:
  400 { "detail": "Not a Wikipedia URL" }
  400 { "detail": "Disambiguation page — provide a more specific URL" }
  400 { "detail": "Article body is empty or could not be parsed" }
  502 { "detail": "LLM or vector DB unavailable" }
```

### POST /chat
```
Request:  { "question": "...", "history": [{"role": "user"|"assistant", "content": "..."}] }
Response: { "answer": "..." }
Errors:
  400 { "detail": "No article loaded. Please ingest an article first." }
  502 { "detail": "LLM unavailable" }
```

### GET /health
```
Response: { "status": "ok" }
```

---

## Container Topology

```yaml
services:
  qdrant:
    image: qdrant/qdrant:v1.8.4
    volumes: [qdrant_storage:/qdrant/storage]
    # not exposed to host — backend reaches it over the internal Docker network

  ollama:
    image: ollama/ollama:latest
    volumes: [ollama_models:/root/.ollama]
    entrypoint: ollama/entrypoint.sh — pulls models then tails server process

  backend:
    build: ./backend          # Python 3.12-slim, non-root user
    environment: [OLLAMA_BASE_URL, QDRANT_HOST, QDRANT_PORT]
    depends_on: [qdrant, ollama]
    # not exposed to host — NGINX reaches it over the internal Docker network

  frontend:
    image: nginx:alpine
    volumes: [./frontend/index.html, ./nginx/nginx.conf]
    ports: ["8080:80"]        # only published port in the whole stack
    depends_on: [backend]
```

Estimated disk after first start: ~2.1 GB (models) + ~350 MB (images) = ~2.45 GB total.

---

## AI-Agent Tooling Used During Development

- Claude Code (claude-sonnet-4-6) — planning, scaffolding, code generation, test writing.
- The running application makes zero calls to any hosted API. All inference is Ollama-local.
