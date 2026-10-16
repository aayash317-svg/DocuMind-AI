import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Query

from backend.app.core.config import settings
from backend.app.ingestion.pipeline import ingestion_pipeline
from backend.app.ingestion.models import DocumentMetadata
from backend.app.retrieval.vector_store import vector_store
from backend.app.retrieval.hybrid import hybrid_retriever
from backend.app.generation.models import ChatRequest, ChatResponse
from backend.app.agents.graph import documind_agent_graph

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


@router.post(
    "/documents/upload",
    response_model=DocumentMetadata,
    status_code=status.HTTP_201_CREATED,
    summary="Upload & Index Document"
)
async def upload_document(file: UploadFile = File(...)) -> DocumentMetadata:
    """Upload a PDF, DOCX, or TXT file, extract text, chunk, embed, and index in Qdrant."""
    filename = file.filename or "unknown.txt"
    suffix = Path(filename).suffix.lower()

    if suffix not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{suffix}'. Allowed formats: .pdf, .docx, .txt"
        )

    # Save to a temporary file for processing
    temp_dir = Path(tempfile.gettempdir()) / "documind_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / f"upload_{filename}"

    try:
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        metadata = ingestion_pipeline.process_file(temp_file, filename)
        return metadata
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ingestion failed: {str(e)}")
    finally:
        if temp_file.exists():
            temp_file.unlink(missing_ok=True)


@router.get("/documents", response_model=List[Dict[str, Any]], summary="List Indexed Documents")
async def list_documents() -> List[Dict[str, Any]]:
    """List all documents currently indexed in the vector store."""
    return vector_store.list_documents()


@router.get("/documents/{document_id}", summary="Get Document Details")
async def get_document(document_id: str) -> Dict[str, Any]:
    """Get metadata and chunk statistics for a specific document."""
    docs = vector_store.list_documents()
    for d in docs:
        if d["document_id"] == document_id:
            return d
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found.")


@router.delete("/documents/{document_id}", summary="Delete Document")
async def delete_document(document_id: str) -> Dict[str, Any]:
    """Remove a document and all its chunks from the vector store."""
    vector_store.delete_document(document_id)
    hybrid_retriever.sync_bm25_index()
    return {"message": f"Document '{document_id}' successfully removed from vector store."}


@router.post("/chat", response_model=ChatResponse, summary="Grounded Chat Query")
async def chat_query(request: ChatRequest) -> ChatResponse:
    """Answer question with evidence-grounded citations via LangGraph agent."""
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
        response = result_state.get("final_response")
        if response:
            return response

        # Fallback if graph did not produce final_response
        draft = result_state.get("draft_answer", "No answer generated.")
        return ChatResponse(
            answer=draft,
            insufficient_evidence=True,
            sources=[]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent workflow error: {str(e)}"
        )

