import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models import Claim
from src.grouping.deduplicator import ClaimDeduplicator


def make_claim(text, quote, source_id, title=None):
    return Claim(
        claim_text=text,
        supporting_quote=quote,
        source_id=source_id,
        source_title=title,
    )


class TestClaimDeduplication:

    def test_empty_claims_returns_empty(self):
        dedup = ClaimDeduplicator()
        assert dedup.deduplicate_and_group([]) == []

    def test_single_claim_returns_one_group(self):
        dedup = ClaimDeduplicator()
        claim = make_claim(
            "The EU AI Act bans real-time biometric identification in public spaces",
            "Article 5 prohibits real-time biometric identification systems",
            "eu_act_summary",
        )
        groups = dedup.deduplicate_and_group([claim])
        assert len(groups) == 1
        assert len(groups[0].claims) == 1

    def test_near_identical_claims_from_different_sources_grouped(self):
        dedup = ClaimDeduplicator(similarity_threshold=0.75)

        claims = [
            make_claim(
                "The EU AI Act categorizes AI systems into risk levels with corresponding requirements",
                "The Act establishes a risk-based approach with four tiers of regulation",
                "source_eu_overview", "EU AI Act Overview",
            ),
            make_claim(
                "The European Union AI Act classifies AI systems by risk tiers and sets requirements accordingly",
                "AI systems are classified into unacceptable, high, limited, and minimal risk categories",
                "source_reuters", "Reuters Analysis",
            ),
            make_claim(
                "China requires generative AI to align with socialist core values",
                "The Interim Measures mandate that AI-generated content adheres to core socialist values",
                "source_china_reg", "China AI Regulation",
            ),
        ]

        groups = dedup.deduplicate_and_group(claims)

        eu_group = None
        for g in groups:
            if any("EU" in c.claim_text or "European" in c.claim_text for c in g.claims):
                eu_group = g
                break

        assert eu_group is not None
        assert len(eu_group.claims) == 2
        assert len(groups) >= 2

    def test_completely_different_claims_stay_separate(self):
        dedup = ClaimDeduplicator(similarity_threshold=0.80)

        claims = [
            make_claim(
                "The EU AI Act will be fully enforced by 2026",
                "Full enforcement is expected to begin in 2026",
                "source_timeline",
            ),
            make_claim(
                "Remote work policies improve employee retention by 25 percent",
                "Companies with flexible work saw 25% better retention rates",
                "source_remote_work",
            ),
            make_claim(
                "Global lithium production doubled between 2020 and 2024",
                "Lithium output grew from 82,000 to 180,000 tonnes",
                "source_mining",
            ),
        ]

        groups = dedup.deduplicate_and_group(claims)
        assert len(groups) == 3

    def test_source_tracking_across_groups(self):
        dedup = ClaimDeduplicator(similarity_threshold=0.70)

        claims = [
            make_claim(
                "AI regulation is necessary to protect public safety and individual rights",
                "Regulation ensures that AI systems do not harm individuals or society",
                "brookings_report",
            ),
            make_claim(
                "Regulation of artificial intelligence is essential for protecting citizens and their rights",
                "AI safety regulation protects public welfare and fundamental rights",
                "eu_commission_paper",
            ),
            make_claim(
                "Strong AI governance frameworks are needed to safeguard public interests and civil liberties",
                "Governance frameworks ensure AI development respects human rights",
                "un_advisory_body",
            ),
        ]

        groups = dedup.deduplicate_and_group(claims)
        largest = max(groups, key=lambda g: len(g.claims))
        assert len(largest.source_ids) >= 2

    def test_total_claims_preserved_after_grouping(self):
        dedup = ClaimDeduplicator(similarity_threshold=0.80)

        claims = [
            make_claim(f"Claim number {i} about topic {i % 3}", f"Evidence for claim {i}", f"src_{i}")
            for i in range(10)
        ]

        groups = dedup.deduplicate_and_group(claims)
        total_in_groups = sum(len(g.claims) for g in groups)
        assert total_in_groups == 10

    def test_high_threshold_creates_more_groups(self):
        dedup_strict = ClaimDeduplicator(similarity_threshold=0.95)
        dedup_loose = ClaimDeduplicator(similarity_threshold=0.60)

        claims = [
            make_claim(
                "AI regulation boosts public trust in technology",
                "Trust increases when clear rules exist",
                "src1",
            ),
            make_claim(
                "Regulation of AI systems increases public confidence",
                "Public confidence grows with regulatory oversight",
                "src2",
            ),
        ]

        strict_groups = dedup_strict.deduplicate_and_group(claims)
        loose_groups = dedup_loose.deduplicate_and_group(claims)

        assert len(strict_groups) >= len(loose_groups)
