import logging
import time

from config.settings import settings

logger = logging.getLogger(__name__)

SUMMARIZE_TEMPLATE = """Summarize the following text concisely. Keep only key facts and claims.
Do not add any information not present in the text.

Text:
---
{text}
---

Concise summary:"""

MAX_BATCH_CHARS = 30000
CALL_DELAY = 22
RATE_LIMIT_DELAY = 60


class ExtractiveSummarizer:

    def __init__(self):
        self._llm = None

    def _load_llm(self):
        if self._llm is not None:
            return

        from langchain_groq import ChatGroq

        self._llm = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model_name=settings.LLM_MODEL,
            temperature=0.0,
            max_tokens=settings.MAX_TOKENS,
        )
        logger.info("Summarizer LLM loaded")

    def summarize_chunks(self, chunks: list[str]) -> str:
        if not chunks:
            return ""

        self._load_llm()

        batches = self._create_batches(chunks)
        logger.info(f"Summarizing {len(chunks)} chunks in {len(batches)} batches")
        print(f"    ({len(chunks)} chunks -> {len(batches)} batches)")

        summaries = []
        for i, batch_text in enumerate(batches):
            if i > 0:
                time.sleep(CALL_DELAY)
            summary = self._summarize_with_retry(batch_text, batch_index=i)
            summaries.append(summary)

        return "\n\n".join(summaries)

    def _create_batches(self, chunks: list[str]) -> list[str]:
        batches = []
        current_batch = []
        current_size = 0

        for chunk in chunks:
            chunk_len = len(chunk)

            if current_size + chunk_len > MAX_BATCH_CHARS and current_batch:
                batches.append("\n\n".join(current_batch))
                current_batch = []
                current_size = 0

            current_batch.append(chunk)
            current_size += chunk_len

        if current_batch:
            batches.append("\n\n".join(current_batch))

        return batches

    def _summarize_with_retry(
        self, text: str, batch_index: int, max_retries: int = 3
    ) -> str:
        if len(text.split()) < 30:
            return text

        for attempt in range(max_retries + 1):
            try:
                from langchain_core.messages import HumanMessage

                response = self._llm.invoke(
                    [HumanMessage(content=SUMMARIZE_TEMPLATE.format(text=text))]
                )
                return response.content.strip()

            except Exception as e:
                error_msg = str(e).lower()
                if "rate" in error_msg or "429" in error_msg or "too many" in error_msg:
                    wait_time = RATE_LIMIT_DELAY * (attempt + 1)
                    logger.warning(
                        f"Rate limited on batch {batch_index}, waiting {wait_time}s (attempt {attempt + 1})"
                    )
                    print(f"    Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                logger.warning(f"Summarization failed for batch {batch_index}: {e}")
                return text[:500]

        logger.error(
            f"Summarization failed for batch {batch_index} after {max_retries + 1} attempts"
        )
        return text[:500]
