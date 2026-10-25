import os
import shutil
import tempfile
import uuid
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Query, Depends

from backend.app.core.config import settings
from backend.app.ingestion.pipeline import ingestion_pipeline
from backend.app.ingestion.models import DocumentMetadata
from backend.app.ingestion.diagnostics import FORMAT_LIMITATIONS, GENERAL_LIMITATIONS
from backend.app.retrieval.vector_store import vector_store
from backend.app.retrieval.hybrid import hybrid_retriever
from backend.app.generation.models import ChatRequest, ChatResponse
from backend.app.agents.graph import documind_agent_graph
from backend.app.auth.service import get_current_user_optional
from backend.app.auth.models import UserResponse
from backend.app.chat.service import ChatHistoryService
from backend.app.db.database import get_db_connection

router = APIRouter()


@router.get("/health", summary="Health Check")
async def health_check() -> Dict[str, Any]:
    """Check service health and local model availability."""
    doc_count = len(vector_store.list_documents())
    return {
        "status": "healthy",
        "app_env": settings.APP_ENV,
        "ollama_model": settings.OLLAMA_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "indexed_documents_count": doc_count,
    }


@router.get("/capabilities/limitations", summary="Document Format Limitations")
async def get_format_limitations() -> Dict[str, Any]:
    """Explain technical disadvantages, extraction limitations, and caveats for PDF and DOCX files."""
    return {
        "title": "DocuMind AI — Document Extraction & Format Limitations Guide",
        "summary": "How document structure affects retrieval quality and grounded answers.",
        "formats": FORMAT_LIMITATIONS,
        "general_limitations": GENERAL_LIMITATIONS,
        "key_takeaways": [
            "Scanned PDFs require OCR; poor image quality may produce broken or garbled text chunks.",
            "Tables with merged cells or complex columns may lose their tabular 2D layout.",
            "Visual images, charts, and diagrams cannot be interpreted without vision models.",
            "Word DOC/DOCX floating textboxes and headers/footers can be extracted out of reading order.",
            "The model will strictly abstain from answering if documents omit the requested facts."
        ]
    }


@router.post(
    "/documents/upload",
    response_model=DocumentMetadata,
    status_code=status.HTTP_201_CREATED,
    summary="Upload & Index Document"
)
async def upload_document(
    file: UploadFile = File(...),
    user: Optional[UserResponse] = Depends(get_current_user_optional)
) -> DocumentMetadata:
    """Upload a PDF, DOCX, TXT, or MD file, extract text, chunk, embed, and index in Qdrant with limitations diagnostics."""
    filename = file.filename or "unknown.txt"
    suffix = Path(filename).suffix.lower()

    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{suffix}'. Allowed formats: .pdf, .docx, .txt, .md"
        )

    user_id = user.id if user else "default_user"

    temp_dir = Path(tempfile.gettempdir()) / "documind_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / f"upload_{filename}"

    try:
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        metadata = ingestion_pipeline.process_file(temp_file, filename, user_id=user_id)
        return metadata
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ingestion failed: {str(e)}")
    finally:
        if temp_file.exists():
            temp_file.unlink(missing_ok=True)


@router.get("/documents", response_model=List[Dict[str, Any]], summary="List Indexed Documents")
async def list_documents(user: Optional[UserResponse] = Depends(get_current_user_optional)) -> List[Dict[str, Any]]:
    """List documents visible to the current user with chunk count and limitations analysis."""
    user_id = user.id if user else "default_user"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        if user:
            cursor.execute(
                """
                SELECT document_id, user_id, filename, file_type, file_size_bytes, total_pages, total_chunks, diagnostics_json, created_at
                FROM user_documents
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user.id,)
            )
        else:
            cursor.execute(
                """
                SELECT document_id, user_id, filename, file_type, file_size_bytes, total_pages, total_chunks, diagnostics_json, created_at
                FROM user_documents
                ORDER BY created_at DESC
                """
            )
        rows = cursor.fetchall()

    if rows:
        results = []
        for r in rows:
            diag = None
            if r["diagnostics_json"]:
                try:
                    diag = json.loads(r["diagnostics_json"])
                except Exception:
                    diag = None

            results.append({
                "document_id": r["document_id"],
                "user_id": r["user_id"],
                "filename": r["filename"],
                "file_type": r["file_type"],
                "file_size_bytes": r["file_size_bytes"],
                "total_pages": r["total_pages"],
                "total_chunks": r["total_chunks"],
                "created_at": r["created_at"],
                "limitations": diag
            })
        return results

    # Fallback to vector_store.list_documents() if SQLite is freshly initialized
    return vector_store.list_documents()


@router.get("/documents/{document_id}", summary="Get Document Details")
async def get_document(
    document_id: str,
    user: Optional[UserResponse] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """Get metadata, limitations, and chunk statistics for a specific document."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_documents WHERE document_id = ?", (document_id,))
        row = cursor.fetchone()
        if row:
            diag = None
            if row["diagnostics_json"]:
                try:
                    diag = json.loads(row["diagnostics_json"])
                except Exception:
                    diag = None
            return {
                "document_id": row["document_id"],
                "user_id": row["user_id"],
                "filename": row["filename"],
                "file_type": row["file_type"],
                "file_size_bytes": row["file_size_bytes"],
                "total_pages": row["total_pages"],
                "total_chunks": row["total_chunks"],
                "limitations": diag
            }

    docs = vector_store.list_documents()
    for d in docs:
        if d["document_id"] == document_id:
            return d
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found.")


@router.delete("/documents/{document_id}", summary="Delete Document")
async def delete_document(
    document_id: str,
    user: Optional[UserResponse] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """Remove a document and all its chunks from the vector store and database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM user_documents WHERE document_id = ?", (document_id,))
        doc_row = cursor.fetchone()
        if doc_row and user and doc_row["user_id"] != user.id and doc_row["user_id"] != "default_user":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied: Cannot delete another user's document."
            )
        cursor.execute("DELETE FROM user_documents WHERE document_id = ?", (document_id,))
        conn.commit()

    vector_store.delete_document(document_id)
    hybrid_retriever.sync_bm25_index()
    return {"message": f"Document '{document_id}' successfully removed."}


@router.post("/chat", response_model=ChatResponse, summary="Grounded Chat Query")
async def chat_query(
    request: ChatRequest,
    user: Optional[UserResponse] = Depends(get_current_user_optional)
) -> ChatResponse:
    """Answer question with evidence-grounded citations and persist to chat history."""
    user_id = user.id if user else "default_user"
    conv_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"

    # Verify conversation ownership if an existing conversation_id is provided
    if request.conversation_id:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM conversations WHERE id = ?", (request.conversation_id,))
            conv_row = cursor.fetchone()
            if conv_row and conv_row["user_id"] != user_id and conv_row["user_id"] != "default_user":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Cannot send message to another user's conversation."
                )

    # Save incoming user question to SQLite history
    ChatHistoryService.save_message(
        conv_id=conv_id,
        user_id=user_id,
        sender="user",
        text=request.question
    )

    initial_state = {
        "question": request.question,
        "document_ids": request.document_ids,
        "top_k": request.top_k,
        "retrieved_passages": [],
        "step_count": 0,
        "is_sufficient": False,
        "draft_answer": "",
        "final_response": None,
    }

    try:
        result_state = await documind_agent_graph.ainvoke(initial_state)
        response: Optional[ChatResponse] = result_state.get("final_response")
        if not response:
            draft = result_state.get("draft_answer", "No answer generated.")
            response = ChatResponse(
                answer=draft,
                insufficient_evidence=True,
                sources=[]
            )

        response.conversation_id = conv_id

        # Save assistant answer and verified citations to SQLite history
        ChatHistoryService.save_message(
            conv_id=conv_id,
            user_id=user_id,
            sender="assistant",
            text=response.answer,
            insufficient_evidence=response.insufficient_evidence,
            sources=response.sources
        )

        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent workflow error: {str(e)}"
        )
