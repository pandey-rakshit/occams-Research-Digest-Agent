import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models import Claim, ClaimGroup
from src.grouping.deduplicator import ClaimDeduplicator


def make_claim(text, quote, source_id, title=None):
    return Claim(
        claim_text=text,
        supporting_quote=quote,
        source_id=source_id,
        source_title=title,
    )


class TestConflictingClaims:

    def test_opposing_views_on_regulation_both_preserved(self):
        dedup = ClaimDeduplicator(similarity_threshold=0.70)

        claims = [
            make_claim(
                "AI regulation stifles innovation and drives companies to less regulated jurisdictions",
                "Compliance costs for SMEs could be particularly burdensome, potentially driving relocation",
                "industry_report", "Tech Industry Report",
            ),
            make_claim(
                "AI regulation promotes innovation by establishing clear rules and building public trust",
                "Clear regulatory frameworks create a level playing field that stimulates innovation",
                "eu_commission", "EU Commission Report",
            ),
        ]

        groups = dedup.deduplicate_and_group(claims)
        all_texts = [c.claim_text for g in groups for c in g.claims]

        assert any("stifles" in t for t in all_texts)
        assert any("promotes" in t for t in all_texts)

    def test_no_claims_dropped_with_mixed_agreement_and_conflict(self):
        dedup = ClaimDeduplicator(similarity_threshold=0.80)

        claims = [
            make_claim(
                "AI will create 97 million new jobs by 2030 according to the World Economic Forum",
                "The WEF estimates 97 million new roles will emerge",
                "wef_report", "WEF Future of Jobs",
            ),
            make_claim(
                "AI automation will displace 85 million jobs globally by 2030",
                "An estimated 85 million jobs will be eliminated through automation",
                "mckinsey_study", "McKinsey Global Institute",
            ),
            make_claim(
                "The net impact of AI on employment remains highly uncertain",
                "Researchers disagree on whether AI will create or destroy more jobs overall",
                "oxford_review", "Oxford Economics Review",
            ),
            make_claim(
                "AI regulation costs could reach billions for the technology sector",
                "Industry estimates compliance costs at $5-10 billion annually",
                "tech_council", "Technology Council Brief",
            ),
        ]

        groups = dedup.deduplicate_and_group(claims)
        total = sum(len(g.claims) for g in groups)
        assert total == 4

    def test_conflicting_claims_within_same_topic_flagged(self):
        dedup = ClaimDeduplicator(similarity_threshold=0.65)

        claims = [
            make_claim(
                "The US voluntary approach to AI governance is effective and innovation-friendly",
                "Voluntary commitments allow rapid innovation while maintaining safety",
                "us_tech_lobby",
            ),
            make_claim(
                "The US voluntary approach to AI governance is insufficient without enforcement",
                "Without enforceable rules companies may not follow through on safety commitments",
                "civil_liberties_org",
            ),
        ]

        groups = dedup.deduplicate_and_group(claims)
        all_texts = [c.claim_text for g in groups for c in g.claims]

        assert any("effective" in t for t in all_texts)
        assert any("insufficient" in t for t in all_texts)

    def test_fallback_digest_includes_all_conflicting_claims(self):
        from src.generation.digest_generator import DigestGenerator

        gen = DigestGenerator.__new__(DigestGenerator)

        groups = [
            ClaimGroup(
                group_id=0,
                theme="Impact of AI Regulation on Innovation",
                claims=[
                    make_claim(
                        "Regulation stifles innovation in the AI sector",
                        "Compliance burden reduces R&D spending",
                        "critic_report", "Industry Critics Report",
                    ),
                    make_claim(
                        "Regulation promotes sustainable innovation in AI",
                        "Clear rules enable long-term investment in safe AI",
                        "supporter_report", "EU Innovation Report",
                    ),
                ],
                source_ids=["critic_report", "supporter_report"],
                is_conflicting=True,
            ),
        ]

        digest = gen._fallback_digest(groups)

        assert "stifles" in digest.lower()
        assert "promotes" in digest.lower()
        assert "conflicting" in digest.lower()
        assert "Industry Critics Report" in digest
        assert "EU Innovation Report" in digest

    def test_large_batch_with_mixed_topics_preserves_everything(self):
        dedup = ClaimDeduplicator(similarity_threshold=0.80)

        topics = [
            ("EU AI Act bans social scoring by governments", "Article 5 prohibits social scoring"),
            ("China requires AI content to align with socialist values", "Generative AI must follow core values"),
            ("US relies on voluntary AI safety commitments", "Major companies made voluntary pledges"),
            ("India is developing its own AI governance framework", "NITI Aayog released AI principles"),
            ("UK positions itself as AI-friendly with light regulation", "The UK aims to attract AI investment"),
            ("Singapore sandbox approach allows controlled AI testing", "Regulatory sandboxes enable innovation"),
            ("Brazil passed its AI regulatory framework in 2024", "Marco Legal da IA was signed into law"),
            ("Japan focuses on AI governance through soft law", "Guidelines rather than binding regulations"),
        ]

        claims = [
            make_claim(text, quote, f"source_{i}")
            for i, (text, quote) in enumerate(topics)
        ]

        groups = dedup.deduplicate_and_group(claims)
        total = sum(len(g.claims) for g in groups)

        assert total == len(topics)
        assert len(groups) >= 5
