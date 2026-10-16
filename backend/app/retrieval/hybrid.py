from typing import List, Dict, Any, Optional
from backend.app.core.config import settings
from backend.app.retrieval.vector_store import vector_store
from backend.app.retrieval.bm25_search import bm25_search
from backend.app.retrieval.rrf import reciprocal_rank_fusion


class HybridRetriever:
    """Orchestrates Dense vector retrieval, BM25 keyword search, and RRF fusion."""

    def __init__(self):
        self._synced = False

    def sync_bm25_index(self) -> None:
        """Loads all chunks from Qdrant into the in-memory BM25 index."""
        all_chunks = vector_store.get_all_chunks()
        bm25_search.update_corpus(all_chunks)
        self._synced = True

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        if not self._synced:
            self.sync_bm25_index()

        # 1. Dense retrieval
        dense_results = vector_store.search_dense(
            query=query,
            top_k=top_k,
            document_ids=document_ids
        )

        # 2. BM25 keyword retrieval
        bm25_results = bm25_search.search(
            query=query,
            top_k=top_k,
            document_ids=document_ids
        )

        # If both are empty (no documents indexed yet)
        if not dense_results and not bm25_results:
            return []

        # If only dense has results
        if not bm25_results:
            return dense_results[:top_k]

        # If only BM25 has results
        if not dense_results:
            return bm25_results[:top_k]

        # 3. Reciprocal Rank Fusion
        fused = reciprocal_rank_fusion(
            ranked_lists=[dense_results, bm25_results],
            k=settings.RRF_K,
            top_n=top_k
        )
        return fused


hybrid_retriever = HybridRetriever()

