import json
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from backend.app.generation.models import CitationSource


class ConversationCreate(BaseModel):
    title: Optional[str] = "New Conversation"


class ConversationUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


class ChatMessageRecord(BaseModel):
    id: str
    conversation_id: str
    sender: str  # 'user' | 'assistant'
    text: str
    insufficient_evidence: bool = False
    sources: List[CitationSource] = Field(default_factory=list)
    created_at: str


class ConversationSummary(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    last_message: Optional[str] = None


class ConversationDetail(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[ChatMessageRecord] = Field(default_factory=list)

