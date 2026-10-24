from backend.app.chat.service import ChatHistoryService
from backend.app.generation.models import CitationSource
from backend.app.db.database import get_db_connection


def test_chat_history_lifecycle():
    user_id = "test_user_history_1"
    
    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, password_hash, salt, full_name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, f"{user_id}@documind.ai", "", "", "Test User", "2026-01-01T00:00:00Z")
        )
        conn.commit()

    # 1. Create conversation
    conv = ChatHistoryService.create_conversation(user_id=user_id, title="Test Exploration")
    assert conv.id.startswith("conv_")
    assert conv.title == "Test Exploration"

    # 2. Save user and assistant messages
    msg1 = ChatHistoryService.save_message(
        conv_id=conv.id,
        user_id=user_id,
        sender="user",
        text="What is the difference between Mel-spectrogram and MFCC?"
    )
    assert msg1.sender == "user"

    msg2 = ChatHistoryService.save_message(
        conv_id=conv.id,
        user_id=user_id,
        sender="assistant",
        text="MFCCs apply the DCT to log Mel filterbank energies [Source: audio.pdf, Page: 4].",
        insufficient_evidence=False,
        sources=[
            CitationSource(
                document_id="doc_1",
                filename="audio.pdf",
                page=4,
                chunk_id="doc_1_p4_c0",
                snippet="DCT decorrelates filterbank energies..."
            )
        ]
    )
    assert msg2.sender == "assistant"
    assert len(msg2.sources) == 1

    # 3. Retrieve conversation history
    detail = ChatHistoryService.get_conversation(conv.id, user_id)
    assert len(detail.messages) == 2
    assert detail.messages[1].sources[0].page == 4

    # 4. Rename conversation
    renamed = ChatHistoryService.rename_conversation(conv.id, user_id, "Audio Signal Processing QA")
    assert renamed.title == "Audio Signal Processing QA"

    # 5. List conversations
    conv_list = ChatHistoryService.list_conversations(user_id)
    assert len(conv_list) >= 1
    assert conv_list[0].id == conv.id

    # 6. Delete conversation
    ChatHistoryService.delete_conversation(conv.id, user_id)
    remaining = ChatHistoryService.list_conversations(user_id)
    assert not any(c.id == conv.id for c in remaining)

