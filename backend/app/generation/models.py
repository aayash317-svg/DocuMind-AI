from typing import List, Optional
from pydantic import BaseModel, Field


class CitationSource(BaseModel):
    """Source reference for evidence citation."""
    document_id: str = Field(..., description="Stable ID of the cited document")
    filename: str = Field(..., description="Original filename of the source document")
    page: int = Field(..., description="Page number where the passage was found")
    chunk_id: str = Field(..., description="Exact chunk identifier")
    snippet: Optional[str] = Field(None, description="Brief snippet of the supporting passage")


class ChatRequest(BaseModel):
    """Incoming user chat query."""
    question: str = Field(..., min_length=2, max_length=2000, description="User question")
    conversation_id: Optional[str] = Field(default=None, description="Optional conversation session ID")
    document_ids: Optional[List[str]] = Field(default=None, description="Optional filter to specific document IDs")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of evidence chunks to retrieve")


class ChatResponse(BaseModel):
    """Grounded chat response with citations."""
    answer: str = Field(..., description="Grounded answer or explanation")
    insufficient_evidence: bool = Field(..., description="True if retrieved documents lack sufficient evidence")
    conversation_id: Optional[str] = Field(default=None, description="Conversation session ID")
    sources: List[CitationSource] = Field(default_factory=list, description="Verified citations")


