import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status

from backend.app.db.database import get_db_connection
from backend.app.chat.models import (
    ConversationSummary,
    ConversationDetail,
    ChatMessageRecord,
)
from backend.app.generation.models import CitationSource


class ChatHistoryService:
    """Manages multi-user chat sessions, message persistence, and retrieval."""

    @classmethod
    def list_conversations(cls, user_id: str) -> List[ConversationSummary]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    c.id, c.user_id, c.title, c.created_at, c.updated_at,
                    COUNT(m.id) as message_count,
                    (SELECT text FROM messages WHERE conversation_id = c.id ORDER BY created_at DESC LIMIT 1) as last_message
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.user_id = ?
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                """,
                (user_id,)
            )
            rows = cursor.fetchall()
            summaries = []
            for r in rows:
                summaries.append(
                    ConversationSummary(
                        id=r["id"],
                        user_id=r["user_id"],
                        title=r["title"],
                        created_at=r["created_at"],
                        updated_at=r["updated_at"],
                        message_count=r["message_count"],
                        last_message=r["last_message"]
                    )
                )
            return summaries

    @classmethod
    def create_conversation(cls, user_id: str, title: Optional[str] = None) -> ConversationDetail:
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        conv_title = title.strip() if title and title.strip() else "New Chat"

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO conversations (id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conv_id, user_id, conv_title, now, now)
            )
            conn.commit()

        return ConversationDetail(
            id=conv_id,
            user_id=user_id,
            title=conv_title,
            created_at=now,
            updated_at=now,
            messages=[]
        )

    @classmethod
    def get_conversation(cls, conv_id: str, user_id: str) -> ConversationDetail:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, user_id, title, created_at, updated_at FROM conversations WHERE id = ? AND user_id = ?",
                (conv_id, user_id)
            )
            conv_row = cursor.fetchone()
            if not conv_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found."
                )

            cursor.execute(
                """
                SELECT id, conversation_id, sender, text, insufficient_evidence, sources_json, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                """,
                (conv_id,)
            )
            msg_rows = cursor.fetchall()

            messages: List[ChatMessageRecord] = []
            for mr in msg_rows:
                sources_data = []
                if mr["sources_json"]:
                    try:
                        raw_sources = json.loads(mr["sources_json"])
                        sources_data = [CitationSource(**s) for s in raw_sources]
                    except Exception:
                        sources_data = []

                messages.append(
                    ChatMessageRecord(
                        id=mr["id"],
                        conversation_id=mr["conversation_id"],
                        sender=mr["sender"],
                        text=mr["text"],
                        insufficient_evidence=bool(mr["insufficient_evidence"]),
                        sources=sources_data,
                        created_at=mr["created_at"]
                    )
                )

            return ConversationDetail(
                id=conv_row["id"],
                user_id=conv_row["user_id"],
                title=conv_row["title"],
                created_at=conv_row["created_at"],
                updated_at=conv_row["updated_at"],
                messages=messages
            )

    @classmethod
    def rename_conversation(cls, conv_id: str, user_id: str, new_title: str) -> ConversationDetail:
        now = datetime.now(timezone.utc).isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (new_title.strip(), now, conv_id, user_id)
            )
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found."
                )
            conn.commit()

        return cls.get_conversation(conv_id, user_id)

    @classmethod
    def delete_conversation(cls, conv_id: str, user_id: str) -> None:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM conversations WHERE id = ? AND user_id = ?",
                (conv_id, user_id)
            )
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found."
                )
            cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            conn.commit()

    @classmethod
    def save_message(
        cls,
        conv_id: str,
        user_id: str,
        sender: str,
        text: str,
        insufficient_evidence: bool = False,
        sources: Optional[List[CitationSource]] = None
    ) -> ChatMessageRecord:
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        sources_json = json.dumps([s.model_dump() for s in (sources or [])]) if sources else None

        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Ensure conversation exists; if not, create it
            cursor.execute("SELECT id, user_id, title FROM conversations WHERE id = ?", (conv_id,))
            row = cursor.fetchone()
            if not row:
                title = text[:40] + ("..." if len(text) > 40 else "")
                cursor.execute(
                    "INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (conv_id, user_id, title, now, now)
                )
            else:
                # Security: Enforce user isolation - prevent posting into another user's conversation
                if row["user_id"] != user_id and row["user_id"] != "default_user" and user_id != "default_user":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: Cannot post messages to another user's conversation."
                    )

                # If first message and title is "New Chat", auto-generate title from user text
                if row["title"] == "New Chat" and sender == "user":
                    auto_title = text[:36] + ("..." if len(text) > 36 else "")
                    cursor.execute(
                        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                        (auto_title, now, conv_id)
                    )
                else:
                    cursor.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))

            cursor.execute(
                """
                INSERT INTO messages (id, conversation_id, user_id, sender, text, insufficient_evidence, sources_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (msg_id, conv_id, user_id, sender, text, int(insufficient_evidence), sources_json, now)
            )
            conn.commit()

        return ChatMessageRecord(
            id=msg_id,
            conversation_id=conv_id,
            sender=sender,
            text=text,
            insufficient_evidence=insufficient_evidence,
            sources=sources or [],
            created_at=now
        )

