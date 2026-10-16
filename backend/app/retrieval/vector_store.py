import os
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sentence_transformers import SentenceTransformer

from backend.app.core.config import settings
from backend.app.ingestion.models import DocumentChunk


class VectorStoreManager:
    """Manages Qdrant local persistence and SentenceTransformer embeddings."""

    _instance = None

    def __init__(self):
        if settings.QDRANT_PATH == ":memory:":
            self.client = QdrantClient(":memory:")
        else:
            Path(settings.QDRANT_PATH).mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=settings.QDRANT_PATH)
        self.collection_name = settings.QDRANT_COLLECTION

        # Lazy/Cached model loading
        self._model: Optional[SentenceTransformer] = None
        self._vector_dim: int = 384
        self._ensure_collection()

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            self._vector_dim = self._model.get_sentence_embedding_dimension()
        return self._model

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=self._vector_dim,
                    distance=qmodels.Distance.COSINE
                )
            )

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        embedding = self.model.encode(query, convert_to_numpy=True, show_progress_bar=False)
        return embedding.tolist()

    def upsert_chunks(self, chunks: List[DocumentChunk]) -> int:
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        embeddings = self.embed_texts(texts)

        points = []
        for chunk, vector in zip(chunks, embeddings):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
            payload = {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "filename": chunk.filename,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
            }
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                )
            )

        # Batch upsert into Qdrant
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        return len(points)

    def search_dense(
        self,
        query: str,
        top_k: int = 10,
        document_ids: Optional[List[str]] = None,
        page_number: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        query_vector = self.embed_query(query)

        conditions = []
        if document_ids:
            conditions.append(
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchAny(any=document_ids)
                )
            )
        if page_number is not None:
            conditions.append(
                qmodels.FieldCondition(
                    key="page_number",
                    match=qmodels.MatchValue(value=page_number)
                )
            )

        query_filter = qmodels.Filter(must=conditions) if conditions else None

        # Use query_points for newer qdrant-client versions
        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True
            ).points
        except Exception:
            # Fallback to search if query_points is unavailable
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True
            )

        formatted_results = []
        for r in results:
            formatted_results.append({
                "chunk_id": r.payload.get("chunk_id", ""),
                "document_id": r.payload.get("document_id", ""),
                "filename": r.payload.get("filename", ""),
                "page": r.payload.get("page_number", 1),
                "chunk_index": r.payload.get("chunk_index", 0),
                "text": r.payload.get("text", ""),
                "score": float(r.score),
                "source_type": "dense"
            })
        return formatted_results

    def get_page_chunks(
        self,
        page_number: int,
        document_ids: Optional[List[str]] = None,
        limit: int = 6
    ) -> List[Dict[str, Any]]:
        """Directly retrieve chunks belonging to a specific page, ordered by chunk_index."""
        conditions = [
            qmodels.FieldCondition(
                key="page_number",
                match=qmodels.MatchValue(value=page_number)
            )
        ]
        if document_ids:
            conditions.append(
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchAny(any=document_ids)
                )
            )

        query_filter = qmodels.Filter(must=conditions)
        try:
            records, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=query_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
        except Exception:
            return []

        page_chunks = []
        for r in records:
            p = r.payload or {}
            page_chunks.append({
                "chunk_id": p.get("chunk_id", ""),
                "document_id": p.get("document_id", ""),
                "filename": p.get("filename", ""),
                "page": p.get("page_number", page_number),
                "chunk_index": p.get("chunk_index", 0),
                "text": p.get("text", ""),
                "score": 0.99,
                "source_type": "page_context"
            })
        page_chunks.sort(key=lambda x: x.get("chunk_index", 0))
        return page_chunks

    def get_all_chunks(self, document_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Retrieve all stored chunk payloads (used for building or refreshing BM25)."""
        offset = None
        all_chunks: List[Dict[str, Any]] = []

        query_filter = None
        if document_ids:
            query_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchAny(any=document_ids)
                    )
                ]
            )

        while True:
            records, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=query_filter,
                limit=200,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            for r in records:
                all_chunks.append({
                    "chunk_id": r.payload.get("chunk_id", ""),
                    "document_id": r.payload.get("document_id", ""),
                    "filename": r.payload.get("filename", ""),
                    "page": r.payload.get("page_number", 1),
                    "chunk_index": r.payload.get("chunk_index", 0),
                    "text": r.payload.get("text", ""),
                })
            if next_offset is None or not records:
                break
            offset = next_offset

        return all_chunks

    def delete_document(self, document_id: str) -> None:
        """Delete all chunks belonging to a document from Qdrant."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=document_id)
                        )
                    ]
                )
            )
        )

    def list_documents(self) -> List[Dict[str, Any]]:
        """List distinct documents indexed in the vector store."""
        chunks = self.get_all_chunks()
        doc_map: Dict[str, Dict[str, Any]] = {}
        for c in chunks:
            doc_id = c["document_id"]
            if doc_id not in doc_map:
                doc_map[doc_id] = {
                    "document_id": doc_id,
                    "filename": c["filename"],
                    "total_chunks": 0,
                    "pages": set(),
                }
            doc_map[doc_id]["total_chunks"] += 1
            doc_map[doc_id]["pages"].add(c["page"])

        return [
            {
                "document_id": v["document_id"],
                "filename": v["filename"],
                "total_chunks": v["total_chunks"],
                "total_pages": len(v["pages"]),
            }
            for v in doc_map.values()
        ]


# Singleton instance
vector_store = VectorStoreManager()

