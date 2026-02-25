# Research Digest Agent — Complete Workflow

## Entry Points

There are two ways to start the application:

| Entry Point | File | How to Run |
|---|---|---|
| CLI | `main.py` | `python main.py --folder sample_inputs` |
| Web UI | `app.py` | `streamlit run app.py` |

Both entry points end up calling the same core: `ResearchDigestOrchestrator.run()`

---

## Full Pipeline Flow

```
User Input (URLs / Files)
        │
        ▼
┌──────────────────┐
│     main.py      │  ← CLI: parses --urls and --folder args
│     app.py       │  ← Streamlit: collects URLs + uploaded files from sidebar
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────┐
│  src/orchestrator.py         │  ← The brain. Calls every step in order.
│  ResearchDigestOrchestrator  │
└────────┬─────────────────────┘
         │
         │  Step 0: RESET (clear vector store, FAISS cache, output dir)
         │
         │  Step 1: INGEST
         ├──────────────────────────────────────┐
         │                                      │
         ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────┐
│ URLFetcher          │              │ LocalFileFetcher     │
│ src/ingestion/      │              │ src/ingestion/       │
│ fetcher.py          │              │ fetcher.py           │
│                     │              │                      │
│ requests.get(url)   │              │ open(file_path)      │
│ BeautifulSoup parse │              │ BeautifulSoup if HTML│
│ Extract title       │              │ Extract title        │
│ Remove <script>,    │              │ Remove noise tags    │
│ <nav>, <footer>     │              │                      │
│                     │              │                      │
│ Output:             │              │ Output:              │
│ ProcessedSource     │              │ ProcessedSource      │
│ (raw_text + meta)   │              │ (raw_text + meta)    │
└─────────┬───────────┘              └──────────┬──────────┘
          │                                     │
          └──────────────┬──────────────────────┘
                         │
                         │  Step 2: CLEAN
                         ▼
              ┌─────────────────────┐
              │ TextCleaner         │
              │ src/ingestion/      │
              │ cleaner.py          │
              │                     │
              │ Remove zero-width   │
              │ Fix smart quotes    │
              │ Collapse whitespace │
              │ Filter noise lines  │
              │ (no regex — uses    │
              │  string ops only)   │
              │                     │
              │ Output:             │
              │ cleaned_text field  │
              └─────────┬───────────┘
                        │
                        │  Step 3: CHUNK
                        ▼
              ┌─────────────────────┐
              │ DocumentChunker     │
              │ src/processing/     │
              │ chunker.py          │
              │                     │
              │ LangChain's         │
              │ Recursive           │
              │ CharacterText       │
              │ Splitter            │
              │                     │
              │ Splits by:          │
              │ \n\n → \n → . →    │
              │ space → char        │
              │                     │
              │ Output:             │
              │ list[DocumentChunk] │
              └─────────┬───────────┘
                        │
                        │  Step 3b: STORE CHUNKS IN FAISS
                        ▼
              ┌─────────────────────┐
              │ FAISSVectorStore    │
              │ src/store/          │
              │ vector_store.py     │
              │                     │
              │ HuggingFaceEmbed-   │
              │ dings (MiniLM-L6)   │
              │ encodes chunks →    │
              │ LangChain FAISS     │
              │                     │
              │ Chunks stored with  │
              │ source_id metadata  │
              │ for later retrieval │
              └─────────┬───────────┘
                        │
                        │  Step 4: SUMMARIZE
                        ▼
              ┌─────────────────────┐
              │ ExtractiveSummarizer│
              │ src/processing/     │
              │ summarizer.py       │
              │                     │
              │ Groq LLM (llama-   │
              │ 3.3-70b) via       │
              │ LangChain           │
              │                     │
              │ Chunks batched up   │
              │ to 30K chars each.  │
              │ 22s delay between   │
              │ batches. Retry on   │
              │ rate limit (60s).   │
              │                     │
              │ Output:             │
              │ summary field per   │
              │ ProcessedSource     │
              └─────────┬───────────┘
                        │
                        │  Step 5: EXTRACT CLAIMS
                        ▼
              ┌─────────────────────┐
              │ ClaimExtractor      │
              │ src/extraction/     │
              │ claim_extractor.py  │
              │                     │
              │ Groq LLM            │
              │ (llama-3.3-70b)     │
              │ via LangChain       │
              │                     │
              │ Sends summary to    │
              │ LLM with structured │
              │ prompt. LLM returns │
              │ JSON array of:      │
              │ {claim, quote}      │
              │                     │
              │ Output:             │
              │ list[Claim] per     │
              │ source              │
              └─────────┬───────────┘
                        │
                        │  Step 6: DEDUPLICATE & GROUP
                        ▼
              ┌─────────────────────┐
              │ ClaimDeduplicator   │
              │ src/grouping/       │
              │ deduplicator.py     │
              │                     │
              │ 1. Encode all claim │
              │    texts via FAISS  │
              │ 2. Find all pairs   │
              │    above threshold  │
              │ 3. Union-Find to    │
              │    build clusters   │
              │ 4. Flag groups with │
              │    multiple sources │
              │    as conflicting   │
              │                     │
              │ Output:             │
              │ list[ClaimGroup]    │
              └─────────┬───────────┘
                        │
                        │  Step 7: GENERATE OUTPUT
                        ▼
              ┌─────────────────────┐
              │ DigestGenerator     │
              │ src/generation/     │
              │ digest_generator.py │
              │                     │
              │ Groq LLM takes      │
              │ grouped claims →    │
              │ themed markdown     │
              │                     │
              │ Also builds         │
              │ sources.json with   │
              │ per-source claims   │
              │                     │
              │ Output:             │
              │ output/digest.md    │
              │ output/sources.json │
              └─────────────────────┘
```

---

## File Responsibilities

### Entry Points

| File | Role |
|---|---|
| `main.py` | CLI interface. Parses `--urls`, `--folder`, `--output` args. Collects file paths. Calls orchestrator. |
| `app.py` | Streamlit web UI. Sidebar for input config. Renders results in tabs (Digest, Claims, Sources, Downloads). |

### Config

| File | Role |
|---|---|
| `config/settings.py` | Single source of truth for all settings: API keys, model names, chunk sizes, thresholds, paths. Reads from `.env`. |
| `config/logging_config.py` | File + console logging setup. Console shows WARNING+ only. File gets full DEBUG log (overwritten each run). Suppresses noisy loggers (httpx, sentence_transformers, huggingface_hub). |

### Data Models

| File | Role |
|---|---|
| `src/models.py` | Defines `SourceMetadata`, `DocumentSection`, `DocumentChunk`, `Claim`, `ClaimGroup`, `ProcessedSource`. Used by every module. |

### Ingestion (`src/ingestion/`)

| File | Role |
|---|---|
| `fetcher.py` | `BaseFetcher` (abstract), `URLFetcher` (requests + BeautifulSoup), `LocalFileFetcher` (file read + optional HTML parse). Returns `ProcessedSource` with raw text and metadata. |
| `cleaner.py` | `TextCleaner` — normalizes text using string operations. No regex. Removes zero-width chars, fixes encoding, collapses whitespace, filters noise lines. |

### Processing (`src/processing/`)

| File | Role |
|---|---|
| `chunker.py` | `DocumentChunker` — wraps LangChain's `RecursiveCharacterTextSplitter`. Splits by paragraph → sentence → word → character boundaries. Returns `list[DocumentChunk]`. |
| `summarizer.py` | `ExtractiveSummarizer` — Groq LLM batch summarization. Batches chunks up to 30K chars, 22s delay between batches, retry with 60s backoff on rate limits. Lazy model loading. |

### Vector Store (`src/store/`)

| File | Role |
|---|---|
| `vector_store.py` | `FAISSVectorStore` — wraps LangChain `FAISS` + `HuggingFaceEmbeddings`. Handles encoding, adding, searching, finding similar pairs via cosine similarity (normalized dot product). Used by both orchestrator (chunk storage) and deduplicator (claim similarity). `clear()` preserves embeddings model to avoid reload. |

### Extraction (`src/extraction/`)

| File | Role |
|---|---|
| `claim_extractor.py` | `ClaimExtractor` — calls Groq LLM via LangChain with a structured prompt. Parses JSON response into `Claim` objects. Each claim has text + supporting quote. |

### Grouping (`src/grouping/`)

| File | Role |
|---|---|
| `deduplicator.py` | `ClaimDeduplicator` — uses `FAISSVectorStore.find_similar_pairs()` to find matching claims. Union-Find algorithm with path compression builds clusters. Flags multi-source groups as conflicting. |

### Generation (`src/generation/`)

| File | Role |
|---|---|
| `digest_generator.py` | `DigestGenerator` — sends grouped claims to Groq LLM for themed markdown output. Has `_fallback_digest()` that works without LLM. Writes `digest.md` and `sources.json`. |

### Orchestrator

| File | Role |
|---|---|
| `src/orchestrator.py` | `ResearchDigestOrchestrator` — the pipeline controller. Receives all dependencies via constructor (dependency injection). Calls: reset → ingest → clean → chunk → store → summarize → extract (22s delay between sources) → deduplicate → generate. Resets vector store, FAISS cache, and output directory on each run. |

### Tests (`tests/`)

| File | What It Tests |
|---|---|
| `test_ingestion.py` | Unreachable URLs, missing files, empty files, HTML parsing, encoding, unsupported types |
| `test_deduplication.py` | Similar claim grouping, distinct claim separation, source tracking, threshold behavior, claim count preservation |
| `test_conflicting_claims.py` | Opposing viewpoints preserved, no claims dropped, fallback digest includes all, large batch handling |

---

## Key Design Decisions

**Why FAISS over in-memory numpy?**
Chunks and claims are stored in a persistent index. Can handle thousands of sources without memory issues. Supports efficient nearest-neighbor search.

**Why Groq over OpenAI/Gemini?**
Free tier, fast inference (Llama 3.3 70B), LangChain integration out of the box.

**Why batch summarization?**
Chunks are grouped into batches (up to 30K chars each) before sending to Groq. This reduces hundreds of API calls to a handful per source, staying within Groq's 30 RPM and 12K TPM limits.

**Why proactive delays (22s) between LLM calls?**
Groq free tier allows 12K tokens per minute. Proactive delays prevent hitting rate limits rather than relying on retry-after-failure.

**Why Union-Find over Agglomerative Clustering?**
Simpler, faster, no sklearn dependency for grouping. Directly works with FAISS similarity pairs.

**Why reset state on each run?**
Vector store, FAISS cache, and output directory are cleared before every run. Previous data must not affect current results since there's no database layer — this is a stateless pipeline.
