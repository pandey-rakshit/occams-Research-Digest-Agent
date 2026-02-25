import logging
import os
from typing import List, Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document as LCDocument
from langchain_huggingface import HuggingFaceEmbeddings

from config.settings import settings
from src.models import DocumentChunk

logger = logging.getLogger(__name__)


class FAISSVectorStore:

    def __init__(self, embedding_model: str = None, faiss_dir: str = None):
        self._model_name = embedding_model or settings.EMBEDDING_MODEL
        self._faiss_dir = faiss_dir or settings.FAISS_DIR
        self._embeddings: Optional[HuggingFaceEmbeddings] = None
        self._store: Optional[FAISS] = None

    def _load_embeddings(self):
        if self._embeddings is not None:
            return

        logger.info(f"Loading embedding model: {self._model_name}")
        self._embeddings = HuggingFaceEmbeddings(model_name=self._model_name)

    def add(self, chunks: List[DocumentChunk]) -> None:
        self._load_embeddings()

        docs = [
            LCDocument(
                page_content=c.content,
                metadata={
                    "document_id": c.document_id,
                    "chunk_id": c.chunk_id,
                    **c.metadata,
                },
            )
            for c in chunks
        ]

        if self._store is None:
            self._store = FAISS.from_documents(docs, embedding=self._embeddings)
        else:
            self._store.add_documents(docs)

        logger.info(
            f"Added {len(chunks)} chunks to FAISS. Total: {self._store.index.ntotal}"
        )

    def search(self, query: str, top_k: int = None) -> List[DocumentChunk]:
        if self._store is None:
            return []

        k = top_k or settings.TOP_K
        docs = self._store.similarity_search(query, k=k)

        return [
            DocumentChunk(
                document_id=d.metadata.get("document_id", ""),
                chunk_id=d.metadata.get("chunk_id", ""),
                content=d.page_content,
                metadata=d.metadata,
            )
            for d in docs
        ]

    def search_with_scores(self, query: str, top_k: int = None) -> List[tuple]:
        if self._store is None:
            return []

        k = top_k or settings.TOP_K
        results = self._store.similarity_search_with_score(query, k=k)

        return [
            (
                DocumentChunk(
                    document_id=doc.metadata.get("document_id", ""),
                    chunk_id=doc.metadata.get("chunk_id", ""),
                    content=doc.page_content,
                    metadata=doc.metadata,
                ),
                float(score),
            )
            for doc, score in results
        ]

    def find_similar_pairs(self, texts: List[str], threshold: float) -> List[tuple]:
        self._load_embeddings()

        embeddings = self._embeddings.embed_documents(texts)

        import numpy as np

        emb_array = np.array(embeddings, dtype=np.float32)
        norms = np.linalg.norm(emb_array, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normalized = emb_array / norms

        sim_matrix = np.dot(normalized, normalized.T)

        pairs = []
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                if sim_matrix[i][j] >= threshold:
                    pairs.append((i, j, float(sim_matrix[i][j])))

        return pairs

    def save(self):
        if self._store is None:
            return

        os.makedirs(self._faiss_dir, exist_ok=True)
        self._store.save_local(self._faiss_dir)
        logger.info(f"Saved FAISS index to {self._faiss_dir}")

    def load(self) -> bool:
        index_path = os.path.join(self._faiss_dir, "index.faiss")
        if not os.path.exists(index_path):
            return False

        self._load_embeddings()
        self._store = FAISS.load_local(
            self._faiss_dir,
            self._embeddings,
            allow_dangerous_deserialization=True,
        )
        logger.info(f"Loaded FAISS index from {self._faiss_dir}")
        return True

    def clear(self):
        self._store = None
        # _embeddings intentionally preserved to avoid reloading model

    @property
    def total_vectors(self) -> int:
        if self._store is None:
            return 0
        return self._store.index.ntotal
