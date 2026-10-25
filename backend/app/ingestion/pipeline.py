import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from backend.app.core.config import settings
from backend.app.ingestion.extractor import DocumentExtractor
from backend.app.ingestion.chunker import DocumentChunker
from backend.app.ingestion.models import DocumentMetadata
from backend.app.ingestion.diagnostics import diagnostic_analyzer
from backend.app.db.database import get_db_connection


class IngestionPipeline:
    """End-to-end ingestion pipeline: extract -> chunk -> embed -> persist -> index with diagnostics."""

    def __init__(self):
        self.chunker = DocumentChunker()

    def process_file(
        self,
        temp_file_path: Path,
        original_filename: str,
        user_id: Optional[str] = "default_user"
    ) -> DocumentMetadata:
        if not DocumentExtractor.is_supported(original_filename):
            raise ValueError(f"Unsupported file type for '{original_filename}'. Supported: PDF, DOCX, TXT, MD.")

        file_size = temp_file_path.stat().st_size
        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if file_size > max_bytes:
            raise ValueError(f"File size ({file_size / (1024*1024):.1f} MB) exceeds limit of {settings.MAX_UPLOAD_MB} MB.")

        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        user_id = user_id or "default_user"

        # 1. Extract text and pages
        extracted_doc = DocumentExtractor.extract(
            file_path=temp_file_path,
            document_id=document_id,
            original_filename=original_filename
        )

        # 2. Chunk document and associate user_id
        chunks = self.chunker.chunk_document(extracted_doc)
        if not chunks:
            raise ValueError(f"Could not generate usable text chunks from '{original_filename}'.")

        for c in chunks:
            c.metadata["user_id"] = user_id

        # 3. Analyze document limitations and extraction diagnostics
        diagnostics = diagnostic_analyzer.analyze(extracted_doc, file_size)

        from backend.app.retrieval.vector_store import vector_store
        from backend.app.retrieval.hybrid import hybrid_retriever

        # 4. Embed & upsert into Qdrant
        vector_store.upsert_chunks(chunks)

        # 5. Sync BM25 keyword index with new content
        hybrid_retriever.sync_bm25_index()

        # 6. Persist uploaded file to durable storage directory
        stored_path = Path(settings.UPLOAD_DIR) / f"{document_id}_{original_filename}"
        with open(temp_file_path, "rb") as src, open(stored_path, "wb") as dst:
            dst.write(src.read())

        now_str = datetime.now(timezone.utc).isoformat()
        diag_dict = diagnostics.model_dump()

        # 7. Record in user_documents SQLite table for multi-tenant tracking
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO user_documents (document_id, user_id, filename, file_type, file_size_bytes, total_pages, total_chunks, diagnostics_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (document_id, user_id, original_filename, extracted_doc.file_type, file_size, extracted_doc.total_pages, len(chunks), json.dumps(diag_dict), now_str)
            )
            conn.commit()

        metadata = DocumentMetadata(
            document_id=document_id,
            user_id=user_id,
            filename=original_filename,
            file_type=extracted_doc.file_type,
            file_size_bytes=file_size,
            total_pages=extracted_doc.total_pages,
            total_chunks=len(chunks),
            upload_timestamp=now_str,
            limitations=diag_dict
        )

        return metadata


ingestion_pipeline = IngestionPipeline()
