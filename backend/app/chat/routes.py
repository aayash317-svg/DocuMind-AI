from fastapi import APIRouter, Depends
from typing import List, Dict, Any

from backend.app.auth.models import UserResponse
from backend.app.auth.service import get_current_user_required
from backend.app.chat.models import (
    ConversationSummary,
    ConversationDetail,
    ConversationCreate,
    ConversationUpdate,
)
from backend.app.chat.service import ChatHistoryService

router = APIRouter(prefix="/conversations", tags=["Chat History"])


@router.get("", response_model=List[ConversationSummary], summary="List Recent Chats")
async def list_user_conversations(
    user: UserResponse = Depends(get_current_user_required)
) -> List[ConversationSummary]:
    """Retrieve all conversations for the authenticated user, ordered by recent activity."""
    return ChatHistoryService.list_conversations(user.id)


@router.post("", response_model=ConversationDetail, summary="Create New Chat")
async def create_new_conversation(
    payload: ConversationCreate,
    user: UserResponse = Depends(get_current_user_required)
) -> ConversationDetail:
    """Start a new chat thread."""
    return ChatHistoryService.create_conversation(user.id, payload.title)


@router.get("/{conv_id}", response_model=ConversationDetail, summary="Get Chat Details")
async def get_conversation_history(
    conv_id: str,
    user: UserResponse = Depends(get_current_user_required)
) -> ConversationDetail:
    """Reopen a conversation and load all messages and citations."""
    return ChatHistoryService.get_conversation(conv_id, user.id)


@router.patch("/{conv_id}", response_model=ConversationDetail, summary="Rename Chat")
async def rename_conversation(
    conv_id: str,
    payload: ConversationUpdate,
    user: UserResponse = Depends(get_current_user_required)
) -> ConversationDetail:
    """Rename a conversation title."""
    return ChatHistoryService.rename_conversation(conv_id, user.id, payload.title)


@router.delete("/{conv_id}", summary="Delete Chat")
async def delete_conversation(
    conv_id: str,
    user: UserResponse = Depends(get_current_user_required)
) -> Dict[str, str]:
    """Delete a conversation and its messages."""
    ChatHistoryService.delete_conversation(conv_id, user.id)
    return {"message": "Conversation successfully deleted."}

