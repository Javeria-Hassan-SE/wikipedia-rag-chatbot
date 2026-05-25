# Wikipedia RAG Chatbot

A containerised, fully local RAG (Retrieval-Augmented Generation) chatbot.  
Paste any Wikipedia URL → the article is chunked, embedded, and stored in Qdrant → ask questions in a persistent multi-turn chat.

All inference runs locally via [Ollama](https://ollama.com/); no external API keys required.

---

## Architecture

```
Browser
  └─► NGINX :8080
        ├─► static  /          → index.html
        └─► proxy   /api/      → FastAPI :8001
                                    ├─► Qdrant  :6333  (vector store)
                                    └─► Ollama  :11434 (embeddings + chat)
```

| Service  | Image / Build        | Role                              |
|----------|----------------------|-----------------------------------|
| frontend | `nginx:alpine`       | Serve SPA + proxy `/api/` to backend |
| backend  | `./backend`          | FastAPI — ingest, embed, retrieve, chat |
| qdrant   | `qdrant/qdrant`      | Vector database                   |
| ollama   | `ollama/ollama`      | Local LLM runtime                 |

**Models used**

| Purpose    | Model          | Size  |
|------------|----------------|-------|
| Embeddings | `all-minilm`   | 22 MB |
| Chat       | `llama3.2:3b`  | 2 GB  |

---

## Quick start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with Compose v2)
- 4 GB RAM free for Ollama models (8 GB recommended)

### Run

```bash
git clone https://github.com/Javeria-Hassan-SE/wikipedia-rag-chatbot.git
cd wikipedia-rag-chatbot
docker compose up
```

On first boot Ollama pulls `all-minilm` (~22 MB) and `llama3.2:3b` (~2 GB) automatically. This takes a few minutes; subsequent starts are instant because the models are cached in a named volume.

Open **http://localhost:8080** in your browser.

### Usage

1. Paste a Wikipedia article URL (e.g. `https://en.wikipedia.org/wiki/Alan_Turing`) into the top input and click **Ingest**.
2. Wait for the success banner — the article has been chunked, embedded, and indexed.
3. Type questions in the chat box. The bot answers from the article with multi-turn context.

---

## API

### `POST /ingest`

```json
{ "url": "https://en.wikipedia.org/wiki/Alan_Turing" }
```

Response `200`:

```json
{ "title": "Alan Turing", "summary": "..." }
```

### `POST /chat`

```json
{
  "question": "Where was Turing born?",
  "history": [
    { "role": "user",      "content": "Who was Alan Turing?" },
    { "role": "assistant", "content": "Alan Turing was a British mathematician..." }
  ]
}
```

Response `200`:

```json
{ "answer": "Alan Turing was born in Maida Vale, London." }
```

### `GET /health`

```json
{ "status": "ok" }
```

---

## Development (local, no Docker)

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

pip install -r requirements-dev.txt

# run tests (unit only, no live services needed)
pytest

# run with coverage
pytest --cov=app --cov-report=term-missing
```

Start the backend against local Ollama + Qdrant:

```bash
# Windows PowerShell
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:QDRANT_HOST     = "localhost"
uvicorn app.main:app --port 8001 --reload
```

---

## Configuration

Copy `.env.example` to `.env` (or set environment variables directly):

| Variable          | Default                  | Description              |
|-------------------|--------------------------|--------------------------|
| `OLLAMA_BASE_URL` | `http://ollama:11434`    | Ollama service URL       |
| `QDRANT_HOST`     | `qdrant`                 | Qdrant hostname          |
| `QDRANT_PORT`     | `6333`                   | Qdrant port              |
| `EMBED_MODEL`     | `all-minilm`             | Ollama embedding model   |
| `CHAT_MODEL`      | `llama3.2:3b`            | Ollama chat model        |

---

## Test coverage

```
Name                           Stmts   Miss  Cover
--------------------------------------------------
app/config.py                      9      0   100%
app/routes/chat.py                21      0   100%
app/routes/ingest.py              25      0   100%
app/services/chunker.py           11      0   100%
app/services/embedder.py          27      0   100%
app/services/llm.py               34      0   100%
app/services/scraper.py           54      2    96%
app/services/vector_store.py      23      0   100%
--------------------------------------------------
TOTAL                            204      2    99%
```

52 unit tests, 3 integration tests (require live services, excluded from default run).

Run integration tests:

```bash
pytest -m integration
```
