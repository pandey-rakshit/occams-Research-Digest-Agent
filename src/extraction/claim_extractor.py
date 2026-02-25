import json
import logging
import re
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from config.settings import settings
from src.models import Claim

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a research analyst. You extract key claims from text. "
    "Every claim must be grounded in the source. Never invent facts. "
    "Return only valid JSON with no extra text."
)

EXTRACTION_TEMPLATE = """Extract 3-7 key claims from this text.
For each claim provide a direct supporting quote from the text.

Return ONLY a JSON array with no additional text:
[{{"claim": "...", "supporting_quote": "..."}}]

Text:
---
{text}
---"""

MAX_RETRIES = 2


class ClaimExtractor:

    def __init__(self):
        self._llm = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model_name=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.MAX_TOKENS,
        )

    def extract_claims(
        self, summary_text: str, source_id: str, source_title: str = None
    ) -> list[Claim]:
        if not summary_text or not summary_text.strip():
            return []

        for attempt in range(MAX_RETRIES + 1):
            try:
                raw_response = self._call_llm(summary_text)
                claims_data = self._parse_response(raw_response)
                return self._build_claims(claims_data, source_id, source_title)

            except json.JSONDecodeError as e:
                logger.warning(
                    f"JSON parse failed for {source_id} (attempt {attempt + 1}): {e}"
                )
                if attempt == MAX_RETRIES:
                    logger.error(
                        f"Claim extraction failed for {source_id} after {MAX_RETRIES + 1} attempts"
                    )
                    return []

            except Exception as e:
                error_msg = str(e).lower()
                if "rate" in error_msg or "429" in error_msg or "too many" in error_msg:
                    wait_time = 60 * (attempt + 1)
                    logger.warning(
                        f"Rate limited for {source_id}, waiting {wait_time}s"
                    )
                    time.sleep(wait_time)
                    continue
                logger.error(f"Claim extraction failed for {source_id}: {e}")
                return []

        return []

    def _call_llm(self, text: str) -> str:

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=EXTRACTION_TEMPLATE.format(text=text)),
        ]
        response = self._llm.invoke(messages)
        return response.content.strip()

    def _parse_response(self, raw_text: str) -> list[dict]:
        cleaned = raw_text
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]

        json_match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group()

        return json.loads(cleaned)

    def _build_claims(
        self, claims_data: list[dict], source_id: str, source_title: str
    ) -> list[Claim]:
        claims = []
        for item in claims_data:
            claim_text = item.get("claim", "").strip()
            if not claim_text:
                continue

            claims.append(
                Claim(
                    claim_text=claim_text,
                    supporting_quote=item.get("supporting_quote", ""),
                    source_id=source_id,
                    source_title=source_title,
                )
            )

        logger.info(f"Extracted {len(claims)} claims from {source_id}")
        return claims
