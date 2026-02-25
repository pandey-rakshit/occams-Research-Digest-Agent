# Research Digest Agent

An autonomous research digest agent that ingests multiple sources, extracts key claims, removes redundancy, and produces a structured, evidence-backed brief.

**Topic:** AI Regulation (5 sample sources included)

## How It Works

1. **Input Handling** — Accepts URLs (fetched via `requests` + `BeautifulSoup` with `lxml` parser) or local `.txt`/`.html` files. Duplicate URLs and file paths are detected and skipped.

2. **Text Cleaning** — Raw text is normalized by removing zero-width characters, collapsing whitespace, fixing smart quotes, and filtering noise lines (nav items, single-word fragments).

3. **Chunking** — Cleaned text is split using LangChain's `RecursiveCharacterTextSplitter` with separators `["\n\n", "\n", ". ", " ", ""]` to preserve paragraph and sentence boundaries. Each chunk gets a UUID identifier.

4. **Embedding + Vector Store** — Chunks are embedded using `sentence-transformers/all-MiniLM-L6-v2` via `HuggingFaceEmbeddings` and stored in an in-memory FAISS index using `langchain_community.vectorstores.FAISS`. Documents accumulate across sources within a single run.

5. **Summarization** — Chunks are batched (up to 30K chars per batch) and summarized via Groq LLM (`llama-3.3-70b-versatile`) through `langchain_groq.ChatGroq`. Batching reduces API calls from hundreds to a handful per source.

6. **Claim Extraction** — Each source's summary is sent to Groq LLM. Returns structured `{claim, supporting_quote}` pairs as JSON. Includes retry logic for malformed JSON and rate limit handling.

7. **Deduplication & Grouping** — All claim texts are embedded and a cosine similarity matrix is computed. Claim pairs above the threshold (default 0.80) are grouped using union-find clustering. Groups with claims from multiple sources are flagged as potentially conflicting.

8. **Digest Generation** — Grouped claims are sent to Groq to produce a themed `digest.md`. A `sources.json` is generated with per-source claims and evidence. Falls back to template-based digest if LLM call fails.

## How Claims Are Grounded

Every claim must include a `supporting_quote` from the source text. The LLM prompt explicitly states: "Never invent facts." Claims without supporting evidence are filtered out during parsing.

## How Deduplication/Grouping Works

Claims are encoded into embeddings via `all-MiniLM-L6-v2`. The cosine similarity matrix is computed by normalizing all vectors to unit length and taking the dot product (`np.dot(normalized, normalized.T)`). Pairs above the threshold are connected using a union-find algorithm with path compression. Each group tracks which sources contribute to it. Groups spanning multiple sources are flagged as conflicting to preserve opposing viewpoints.

## Groq API Rate Limits (Free Tier)

Using `llama-3.3-70b-versatile`:

| Limit | Value |
|-------|-------|
| RPM (Requests per minute) | 30 |
| RPD (Requests per day) | 1,000 |
| TPM (Tokens per minute) | 12,000 |
| TPD (Tokens per day) | 100,000 |

The TPD (100K tokens/day) is the practical constraint. Small `.txt` files (2-6K chars each) work well within limits. Large documents like Wikipedia articles (~50K+ chars) can exhaust daily token quota in 2-3 articles. The pipeline includes proactive delays between API calls (22s) and retry with 60s backoff on rate limit errors.

## One Limitation

100K tokens per day on Groq free tier limits throughput to a few large documents per day. The pipeline handles rate limiting gracefully (waits and retries) but cannot bypass daily quotas.

## One Improvement With More Time

Add confidence scoring per claim by cross-referencing source count: claims supported by multiple independent sources get higher confidence. Also add incremental processing to skip re-processing unchanged sources across runs.

## Setup & Run

```bash
uv add -r requirements.txt

cp .env.example .env
# Add your GROQ_API_KEY to .env

# CLI
python main.py --folder sample_inputs
python main.py --urls https://example.com/article1 https://example.com/article2
python main.py --urls https://example.com/article1 --folder sample_inputs

# Streamlit
streamlit run app.py

# Tests
pytest tests/ -v
```

## Output

- `output/digest.md` — Structured research brief organized by themes with source references
- `output/sources.json` — Machine-readable data: every source with metadata, claims, and supporting quotes
- `logs/pipeline.log` — Full debug log for the run (overwritten each run)

## Project Structure

```
├── app.py                         # Streamlit frontend
├── main.py                        # CLI entry point
├── config/
│   ├── settings.py                # Centralized configuration (UPPERCASE, frozen dataclass)
│   └── logging_config.py          # File + console logging setup
├── src/
│   ├── models.py                  # Data models (ProcessedSource, DocumentChunk, Claim, ClaimGroup)
│   ├── orchestrator.py            # Pipeline controller with dependency injection
│   ├── ingestion/
│   │   ├── fetcher.py             # BaseFetcher → URLFetcher + LocalFileFetcher
│   │   └── cleaner.py             # Text cleaning without regex
│   ├── processing/
│   │   ├── chunker.py             # DocumentChunker (LangChain RecursiveCharacterTextSplitter)
│   │   └── summarizer.py          # Batch summarization via Groq LLM
│   ├── extraction/
│   │   └── claim_extractor.py     # Groq LLM claim extraction with retry
│   ├── grouping/
│   │   └── deduplicator.py        # Cosine similarity + union-find clustering
│   ├── store/
│   │   └── vector_store.py        # FAISSVectorStore (LangChain FAISS + HuggingFaceEmbeddings)
│   └── generation/
│       └── digest_generator.py    # digest.md + sources.json generation
├── tests/
│   ├── test_ingestion.py          # Source handling and cleaning tests
│   ├── test_deduplication.py      # Dedup correctness and threshold tests
│   └── test_conflicting_claims.py # Conflict preservation and fallback tests
├── sample_inputs/                 # 5 AI regulation sample sources
├── data/                          # Runtime: FAISS index (cleared per run)
├── output/                        # Generated digest.md + sources.json
└── logs/                          # pipeline.log (overwritten per run)
```

## Tech Stack

- **LLM:** Groq (`llama-3.3-70b-versatile`) via `langchain-groq`
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` via `langchain-huggingface`
- **Vector Store:** FAISS via `langchain-community`
- **Chunking:** `langchain-text-splitters`
- **Web Scraping:** `requests` + `beautifulsoup4` + `lxml`
- **Frontend:** Streamlit
- **Testing:** pytest

## Tests

- **test_ingestion.py** — Unreachable URLs, missing files, empty content, HTML parsing, encoding, whitespace collapsing
- **test_deduplication.py** — Duplicate grouping, distinct claim separation, threshold behavior, claim count preservation
- **test_conflicting_claims.py** — Opposing viewpoint preservation, large batch handling, fallback digest generation
