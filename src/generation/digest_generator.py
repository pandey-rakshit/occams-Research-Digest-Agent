import json
import logging
import os
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from config.settings import settings
from src.models import ClaimGroup, ProcessedSource

logger = logging.getLogger(__name__)

DIGEST_SYSTEM = (
    "You are a research analyst writing a structured research brief. "
    "Organize findings by thematic sections. Reference sources clearly. "
    "Preserve conflicting viewpoints with attribution. Never invent facts."
)

DIGEST_TEMPLATE = """Generate a markdown research digest from these grouped claims.

Grouped Claims:
{claims_json}

Sources:
{sources_json}

Write the digest with themed sections and source references."""


class DigestGenerator:

    def __init__(self):
        self._llm = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model_name=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.MAX_TOKENS,
        )

    def generate(
        self,
        claim_groups: list[ClaimGroup],
        processed_sources: list[ProcessedSource],
        output_dir: str = None,
    ) -> tuple[str, dict]:
        output_dir = output_dir or settings.OUTPUT_DIR
        os.makedirs(output_dir, exist_ok=True)

        digest_md = self._build_digest(claim_groups, processed_sources)
        sources_json = self._build_sources_json(processed_sources)

        self._write_file(os.path.join(output_dir, "digest.md"), digest_md)
        self._write_json(os.path.join(output_dir, "sources.json"), sources_json)

        return digest_md, sources_json

    def _build_digest(
        self, claim_groups: list[ClaimGroup], sources: list[ProcessedSource]
    ) -> str:
        claims_data = self._prepare_claims_data(claim_groups)
        sources_data = self._prepare_sources_data(sources)

        try:
            content = self._call_llm(claims_data, sources_data)
        except Exception as e:
            logger.error(f"LLM digest generation failed: {e}")
            content = self._fallback_digest(claim_groups)

        header = self._build_header(sources, claim_groups)
        return header + content

    def _call_llm(self, claims_data: list, sources_data: list) -> str:
        messages = [
            SystemMessage(content=DIGEST_SYSTEM),
            HumanMessage(
                content=DIGEST_TEMPLATE.format(
                    claims_json=json.dumps(claims_data, indent=2),
                    sources_json=json.dumps(sources_data, indent=2),
                )
            ),
        ]
        response = self._llm.invoke(messages)
        return response.content.strip()

    def _prepare_claims_data(self, claim_groups: list[ClaimGroup]) -> list[dict]:
        result = []
        for group in claim_groups:
            result.append(
                {
                    "theme": group.theme,
                    "is_conflicting": group.is_conflicting,
                    "claims": [
                        {
                            "claim": c.claim_text,
                            "supporting_quote": c.supporting_quote,
                            "source": c.source_title or c.source_id,
                        }
                        for c in group.claims
                    ],
                    "sources": group.source_ids,
                }
            )
        return result

    def _prepare_sources_data(self, sources: list[ProcessedSource]) -> list[dict]:
        return [
            {
                "id": s.metadata.source_id,
                "title": s.metadata.title or s.metadata.source_path,
                "type": s.metadata.source_type,
            }
            for s in sources
            if s.metadata.status == "success"
        ]

    def _build_header(
        self, sources: list[ProcessedSource], groups: list[ClaimGroup]
    ) -> str:
        successful = sum(1 for s in sources if s.metadata.status == "success")
        total_claims = sum(len(g.claims) for g in groups)

        return (
            f"# Research Digest\n\n"
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**Sources Analyzed:** {successful}\n"
            f"**Total Claims:** {total_claims}\n"
            f"**Claim Groups:** {len(groups)}\n\n---\n\n"
        )

    def _fallback_digest(self, claim_groups: list[ClaimGroup]) -> str:
        sections = []
        for group in claim_groups:
            lines = [f"## {group.theme}\n"]

            for claim in group.claims:
                source_label = claim.source_title or claim.source_id
                lines.append(f"- **{claim.claim_text}**")
                lines.append(f'  > "{claim.supporting_quote}"')
                lines.append(f"  — *{source_label}*\n")

            if group.is_conflicting:
                lines.append(
                    "*Note: This group contains potentially conflicting viewpoints.*\n"
                )

            sections.append("\n".join(lines))

        return "\n\n".join(sections)

    def _build_sources_json(self, sources: list[ProcessedSource]) -> dict:
        return {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_sources": len(sources),
                "successful_sources": sum(
                    1 for s in sources if s.metadata.status == "success"
                ),
            },
            "sources": [
                {
                    "source_id": s.metadata.source_id,
                    "title": s.metadata.title,
                    "source_type": s.metadata.source_type,
                    "source_path": s.metadata.source_path,
                    "status": s.metadata.status,
                    "char_length": s.metadata.char_length,
                    "error": s.metadata.error_message,
                    "claims": [
                        {
                            "claim": c.claim_text,
                            "supporting_quote": c.supporting_quote,
                            "confidence": c.confidence,
                        }
                        for c in s.claims
                    ],
                }
                for s in sources
            ],
        }

    def _write_file(self, path: str, content: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Written: {path}")

    def _write_json(self, path: str, data: dict):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Written: {path}")
