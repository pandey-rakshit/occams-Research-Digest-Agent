import logging
import uuid
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import settings
from src.models import DocumentChunk, DocumentSection

logger = logging.getLogger(__name__)


class DocumentChunker:

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size or settings.CHUNK_SIZE,
            chunk_overlap=chunk_overlap or settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def chunk(self, sections: List[DocumentSection]) -> List[DocumentChunk]:
        chunks = []
        for section in sections:
            texts = self._splitter.split_text(section.content)
            for idx, text in enumerate(texts):
                if not text.strip():
                    continue
                chunks.append(
                    DocumentChunk(
                        document_id=section.document_id,
                        chunk_id=str(uuid.uuid4()),
                        content=text,
                        metadata={
                            **section.metadata,
                            "section": section.section_name,
                            "chunk_index": idx,
                        },
                    )
                )

        logger.info(f"Created {len(chunks)} chunks from {len(sections)} sections")
        return chunks

    def chunk_text(self, text: str, document_id: str) -> List[DocumentChunk]:
        section = DocumentSection(
            document_id=document_id,
            section_name="full_text",
            content=text,
        )
        return self.chunk([section])
