# NOTES.md — Engineering Retrospective

Honest notes on what I'd change and what the AI-assisted workflow got wrong.

---

## What I'd Change With More Time

**Streaming responses**
The single biggest UX improvement. `llama3.2:3b` at CPU speed takes 10–30 s per answer. Streaming the tokens as they arrive (Ollama supports `stream: true`) would make the wait feel much shorter. Skipped to keep scope tight; the implementation is a straightforward SSE route.

**Proper `depends_on` health checks**
The `depends_on` in `docker-compose.yml` only waits for container start, not service readiness. On first boot, Ollama pulls ~2 GB of models before it accepts requests, so the backend may start, connect to Qdrant fine, then fail its first embed call because Ollama isn't ready yet. The right fix is a `healthcheck:` on the Ollama service and `condition: service_healthy` in `depends_on`. Left out because writing a reliable health check for Ollama's model-pull phase is non-trivial.

**Qdrant client lifecycle**
`_get_client()` in `vector_store.py` opens a new gRPC/REST connection on every function call. For this workload (one request per user action) it's harmless, but in a real service you'd want a module-level singleton with reconnect logic.

**Parallel embedding**
`embed_batch` in `embedder.py` calls Ollama sequentially — one request per chunk. Ollama doesn't expose a native batch-embed endpoint, but concurrent `asyncio.gather` calls would halve ingestion time. Skipped to keep error handling simple.

**Multi-article support**
The collection is dropped and recreated on each ingest. Adding a collection-per-URL keyed on the article slug would let users switch between ingested articles without re-fetching. One extra route + a collection-list call in Qdrant.

**URL validation**
The scraper only checks `en.wikipedia.org` is in the URL string. A URL like `https://evil.com?redirect=en.wikipedia.org` would pass. A proper check would parse the URL with `urllib.parse` and assert the netloc exactly.

---

## What the AI Got Wrong

**Package versions that didn't exist**
The AI's initial `requirements.txt` specified `uvicorn==0.34.0`, `qdrant-client==1.13.2`, and `langchain-text-splitters==0.3.8` — none of which existed on PyPI. Had to run `pip index versions` for each package and pin to the highest available. The AI has a training-data cutoff and guessed plausible-sounding future versions.

**Python 3.8 type hint compatibility**
The AI wrote `list[ChatMessage]` in Pydantic model fields — valid Python 3.10+ syntax. At runtime on Python 3.8 uvicorn raised `TypeError: 'type' object is not subscriptable`. The fix required `from typing import List` and `List[ChatMessage]` in `models.py`. The `from __future__ import annotations` the AI applied to other files doesn't help Pydantic v2, which evaluates annotations at class construction.

**RAG score threshold too aggressive**
The AI set `score_threshold=0.3` based on typical embedding model behaviour. `all-minilm` at 22 MB produces lower absolute cosine scores than larger models — most relevant chunks scored 0.15–0.25. The bot was silently returning zero chunks for many questions, making it look broken. Caught during manual testing; fixed by lowering to 0.1 and raising `top_k` from 5 to 8.

**`env_file: .env` in docker-compose**
The AI added `env_file: .env` to the backend service. Docker Compose fails hard if the referenced file doesn't exist. Since all vars have defaults in `config.py` and are also set explicitly in the `environment:` block, the `env_file` line was redundant and risky for a reviewer doing a cold clone. Removed.

**Windows BOM on `.env` files**
The AI's initial `config.py` used `env_file_encoding="utf-8"`. PowerShell writes UTF-8 files with a Byte Order Mark; pydantic-settings read the key as `﻿QDRANT_HOST` instead of `QDRANT_HOST` and raised `Extra inputs are not permitted`. Fixed by switching to `utf-8-sig`, which silently strips the BOM.

---

## Known Limitations and Fragilities

- **Wikipedia HTML structure** — the scraper relies on `#mw-content-text p` and the `dmbox-disambig` class. A Wikipedia HTML refactor would break it silently (empty article body) or noisily (wrong parse).
- **English only** — prompts and citation-stripping regex (`\[\d+\]`) are tuned for English Wikipedia.
- **No concurrent user isolation** — a second user ingesting a different article while the first is mid-chat will invalidate that chat's vector store silently.
- **Local GPU not used** — the Ollama container runs on CPU. On machines where Docker cannot pass through the GPU, inference is slow (~20 s/response). Users with an Nvidia GPU and `nvidia-container-toolkit` installed can add `deploy: resources: reservations: devices:` to the ollama service.
