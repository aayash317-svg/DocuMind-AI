import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from backend.app.core.config import settings
from backend.app.ingestion.extractor import DocumentExtractor
from backend.app.ingestion.chunker import DocumentChunker
from backend.app.ingestion.models import DocumentMetadata
from backend.app.retrieval.vector_store import vector_store
from backend.app.retrieval.hybrid import hybrid_retriever


class IngestionPipeline:
    """End-to-end ingestion pipeline: extract -> chunk -> embed -> persist -> index."""

    def __init__(self):
        self.chunker = DocumentChunker()

    def process_file(self, temp_file_path: Path, original_filename: str) -> DocumentMetadata:
        if not DocumentExtractor.is_supported(original_filename):
            raise ValueError(f"Unsupported file type for '{original_filename}'. Supported: PDF, DOCX, TXT.")

        file_size = temp_file_path.stat().st_size
        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if file_size > max_bytes:
            raise ValueError(f"File size ({file_size / (1024*1024):.1f} MB) exceeds limit of {settings.MAX_UPLOAD_MB} MB.")

        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        
        # 1. Extract text and pages
        extracted_doc = DocumentExtractor.extract(
            file_path=temp_file_path,
            document_id=document_id,
            original_filename=original_filename
        )

        # 2. Chunk document
        chunks = self.chunker.chunk_document(extracted_doc)
        if not chunks:
            raise ValueError(f"Could not generate usable text chunks from '{original_filename}'.")

        # 3. Embed & upsert into Qdrant
        vector_store.upsert_chunks(chunks)

        # 4. Sync BM25 keyword index with new content
        hybrid_retriever.sync_bm25_index()

        # 5. Persist uploaded file to durable storage directory
        stored_path = Path(settings.UPLOAD_DIR) / f"{document_id}_{original_filename}"
        with open(temp_file_path, "rb") as src, open(stored_path, "wb") as dst:
            dst.write(src.read())

        metadata = DocumentMetadata(
            document_id=document_id,
            filename=original_filename,
            file_type=extracted_doc.file_type,
            file_size_bytes=file_size,
            total_pages=extracted_doc.total_pages,
            total_chunks=len(chunks),
            upload_timestamp=datetime.now(timezone.utc).isoformat()
        )

        return metadata


ingestion_pipeline = IngestionPipeline()

