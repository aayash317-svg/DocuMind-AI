from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DocumentPage(BaseModel):
    """Represents an extracted page or logical section of a document."""
    page_number: int = Field(..., description="1-indexed page or section number")
    text: str = Field(..., description="Raw text content of the page")


class ExtractedDocument(BaseModel):
    """Represents full extraction output of a document."""
    document_id: str
    filename: str
    file_type: str
    total_pages: int
    pages: List[DocumentPage]


class DocumentChunk(BaseModel):
    """Represents a text chunk ready for vector embedding and retrieval."""
    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    chunk_index: int
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentMetadata(BaseModel):
    """Stored document metadata."""
    document_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    total_pages: int
    total_chunks: int
    upload_timestamp: str

