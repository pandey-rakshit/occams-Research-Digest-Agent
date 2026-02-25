import logging
import os
import shutil

from config.settings import settings
from src.extraction.claim_extractor import ClaimExtractor
from src.generation.digest_generator import DigestGenerator
from src.grouping.deduplicator import ClaimDeduplicator
from src.ingestion.cleaner import TextCleaner
from src.ingestion.fetcher import LocalFileFetcher, URLFetcher
from src.models import Claim, ProcessedSource
from src.processing.chunker import DocumentChunker
from src.processing.summarizer import ExtractiveSummarizer
from src.store.vector_store import FAISSVectorStore

logger = logging.getLogger(__name__)


class ResearchDigestOrchestrator:

    def __init__(
        self,
        url_fetcher: URLFetcher = None,
        local_fetcher: LocalFileFetcher = None,
        cleaner: TextCleaner = None,
        chunker: DocumentChunker = None,
        summarizer: ExtractiveSummarizer = None,
        claim_extractor: ClaimExtractor = None,
        deduplicator: ClaimDeduplicator = None,
        digest_generator: DigestGenerator = None,
        vector_store: FAISSVectorStore = None,
    ):
        self._url_fetcher = url_fetcher or URLFetcher()
        self._local_fetcher = local_fetcher or LocalFileFetcher()
        self._cleaner = cleaner or TextCleaner()
        self._chunker = chunker or DocumentChunker()
        self._summarizer = summarizer or ExtractiveSummarizer()
        self._claim_extractor = claim_extractor or ClaimExtractor()
        self._vector_store = vector_store or FAISSVectorStore()
        self._deduplicator = deduplicator or ClaimDeduplicator(
            vector_store=self._vector_store
        )
        self._digest_generator = digest_generator or DigestGenerator()

    def run(
        self,
        urls: list[str] = None,
        local_paths: list[str] = None,
        output_dir: str = "output",
    ) -> dict:
        urls = urls or []
        local_paths = local_paths or []

        if not urls and not local_paths:
            raise ValueError("Provide at least one URL or local file path.")

        self._reset(output_dir)

        logger.info(f"Starting pipeline: {len(urls)} URLs, {len(local_paths)} files")
        print(f"[*] Processing {len(urls)} URLs and {len(local_paths)} local files...")

        sources = self._ingest(urls, local_paths)
        valid = self._clean_sources(sources)

        if not valid:
            return self._error_result("No valid sources to process.", sources)

        print(f"[*] Summarizing {len(valid)} sources...")
        self._summarize_sources(valid)

        print("[*] Extracting claims...")
        all_claims = self._extract_all_claims(valid)

        if not all_claims:
            return self._error_result("No claims could be extracted.", sources)

        print("[*] Grounding claims with source text...")
        self._ground_claims(all_claims)

        print(f"[*] Grouping {len(all_claims)} claims...")
        groups = self._deduplicator.deduplicate_and_group(all_claims)

        print("[*] Generating digest...")
        digest_md, sources_json = self._digest_generator.generate(
            groups, sources, output_dir
        )

        print(f"[+] Done! {len(all_claims)} claims in {len(groups)} groups.")

        return {
            "status": "success",
            "sources": sources,
            "claim_groups": groups,
            "total_claims": len(all_claims),
            "digest_md": digest_md,
            "sources_json": sources_json,
        }

    def _reset(self, output_dir: str):
        self._vector_store.clear()

        faiss_dir = settings.FAISS_DIR
        if os.path.exists(faiss_dir):
            shutil.rmtree(faiss_dir)

        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)

        logger.info("Reset: cleared vector store, FAISS cache, and output directory")

    def _ingest(self, urls: list[str], local_paths: list[str]) -> list[ProcessedSource]:
        sources = []
        seen = set()

        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            sources.append(self._url_fetcher.fetch(url))

        for path in local_paths:
            abs_path = os.path.abspath(path)
            if abs_path in seen:
                continue
            seen.add(abs_path)
            sources.append(self._local_fetcher.fetch(path))

        logger.info(f"Ingested {len(sources)} sources")
        return sources

    def _clean_sources(self, sources: list[ProcessedSource]) -> list[ProcessedSource]:
        valid = []
        for source in sources:
            if source.metadata.status != "success":
                continue

            source.cleaned_text = self._cleaner.clean(source.raw_text)

            if not source.cleaned_text:
                source.metadata.status = "empty"
                continue

            valid.append(source)

        logger.info(f"{len(valid)} valid sources after cleaning")
        return valid

    def _summarize_sources(self, sources: list[ProcessedSource]):
        for source in sources:
            doc_chunks = self._chunker.chunk_text(
                source.cleaned_text, source.metadata.source_id
            )
            source.chunks = doc_chunks

            if doc_chunks:
                self._vector_store.add(doc_chunks)

            chunk_texts = [chunk.content for chunk in doc_chunks]
            source.summary = self._summarizer.summarize_chunks(chunk_texts)

        logger.info("Summarization complete")

    def _extract_all_claims(self, sources: list[ProcessedSource]) -> list[Claim]:
        import time

        all_claims = []

        for i, source in enumerate(sources):
            if i > 0:
                time.sleep(22)
            claims = self._claim_extractor.extract_claims(
                source.summary,
                source.metadata.source_id,
                source.metadata.title,
            )
            source.claims = claims
            all_claims.extend(claims)

        logger.info(f"Extracted {len(all_claims)} total claims")
        return all_claims

    def _ground_claims(self, claims: list[Claim]):
        for claim in claims:
            results = self._vector_store.search(claim.claim_text, top_k=3)

            matched = [
                r for r in results
                if r.metadata.get("document_id") == claim.source_id
            ]

            if matched:
                claim.supporting_quote = matched[0].content

        logger.info(f"Grounded {len(claims)} claims with source text from vector store")

    def _error_result(self, message: str, sources: list[ProcessedSource]) -> dict:
        logger.error(message)
        return {"status": "error", "message": message, "sources": sources}
