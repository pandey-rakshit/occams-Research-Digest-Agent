from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SourceMetadata:
    source_id: str
    source_type: str
    source_path: str
    title: Optional[str] = None
    char_length: int = 0
    status: str = "success"
    error_message: Optional[str] = None


@dataclass
class DocumentSection:
    document_id: str
    section_name: str
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class DocumentChunk:
    document_id: str
    chunk_id: str
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Claim:
    claim_text: str
    supporting_quote: str
    source_id: str
    source_title: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class ClaimGroup:
    group_id: int
    theme: str
    claims: list[Claim] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    is_conflicting: bool = False


@dataclass
class ProcessedSource:
    metadata: SourceMetadata
    raw_text: str = ""
    cleaned_text: str = ""
    summary: str = ""
    sections: list[DocumentSection] = field(default_factory=list)
    chunks: list[DocumentChunk] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
