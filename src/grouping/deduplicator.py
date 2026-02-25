import logging
from collections import defaultdict

from config.settings import settings
from src.models import Claim, ClaimGroup, DocumentChunk
from src.store.vector_store import FAISSVectorStore

logger = logging.getLogger(__name__)


class ClaimDeduplicator:

    def __init__(
        self, similarity_threshold: float = None, vector_store: FAISSVectorStore = None
    ):
        self._threshold = similarity_threshold or settings.SIMILARITY_THRESHOLD
        self._store = vector_store or FAISSVectorStore()

    def deduplicate_and_group(self, claims: list[Claim]) -> list[ClaimGroup]:
        if not claims:
            return []

        if len(claims) == 1:
            return [self._single_claim_group(claims[0])]

        claim_texts = [c.claim_text for c in claims]
        similar_pairs = self._store.find_similar_pairs(claim_texts, self._threshold)
        labels = self._build_clusters(len(claims), similar_pairs)

        self._store_claims_in_index(claims)

        groups = self._assemble_groups(claims, labels)
        self._flag_conflicts(groups)

        result = sorted(groups, key=lambda g: len(g.claims), reverse=True)
        logger.info(f"Grouped {len(claims)} claims into {len(result)} groups")
        return result

    def _single_claim_group(self, claim: Claim) -> ClaimGroup:
        return ClaimGroup(
            group_id=0,
            theme=claim.claim_text,
            claims=[claim],
            source_ids=[claim.source_id],
        )

    def _build_clusters(self, n: int, pairs: list[tuple[int, int, float]]) -> list[int]:
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for i, j, _ in pairs:
            union(i, j)

        root_to_label = {}
        labels = []
        for i in range(n):
            root = find(i)
            if root not in root_to_label:
                root_to_label[root] = len(root_to_label)
            labels.append(root_to_label[root])

        return labels

    def _store_claims_in_index(self, claims: list[Claim]):
        chunks = [
            DocumentChunk(
                document_id=c.source_id,
                chunk_id=f"claim_{i}",
                content=c.claim_text,
                metadata={"source_title": c.source_title, "claim": c.claim_text},
            )
            for i, c in enumerate(claims)
        ]
        self._store.add(chunks)

    def _assemble_groups(
        self, claims: list[Claim], labels: list[int]
    ) -> list[ClaimGroup]:
        groups_map = defaultdict(lambda: {"claims": [], "source_ids": set()})

        for claim, label in zip(claims, labels):
            groups_map[label]["claims"].append(claim)
            groups_map[label]["source_ids"].add(claim.source_id)

        groups = []
        for group_id, data in groups_map.items():
            groups.append(
                ClaimGroup(
                    group_id=group_id,
                    theme=data["claims"][0].claim_text,
                    claims=data["claims"],
                    source_ids=list(data["source_ids"]),
                )
            )

        return groups

    def _flag_conflicts(self, groups: list[ClaimGroup]):
        for group in groups:
            if len(group.claims) < 2:
                continue

            unique_sources = set(c.source_id for c in group.claims)
            if len(unique_sources) >= 2:
                group.is_conflicting = True
