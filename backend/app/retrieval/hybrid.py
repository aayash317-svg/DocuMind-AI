import re
from typing import List, Dict, Any, Optional
from backend.app.core.config import settings
from backend.app.retrieval.vector_store import vector_store
from backend.app.retrieval.bm25_search import bm25_search
from backend.app.retrieval.rrf import reciprocal_rank_fusion


class HybridRetriever:
    """Orchestrates Dense vector retrieval, BM25 keyword search, and RRF fusion with page awareness."""

    def __init__(self):
        self._synced = False

    def sync_bm25_index(self) -> None:
        """Loads all chunks from Qdrant into the in-memory BM25 index."""
        all_chunks = vector_store.get_all_chunks()
        bm25_search.update_corpus(all_chunks)
        self._synced = True

    @staticmethod
    def extract_target_page(query: str) -> Optional[int]:
        """Detect if the user is asking about a specific page (e.g. 'page 4', 'pg 2', 'p. 5')."""
        match = re.search(r"\b(?:page|pg|p\.)\s*:?\s*(\d+)\b", query, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        if not self._synced:
            self.sync_bm25_index()

        target_page = self.extract_target_page(query)

        # 1. Dense retrieval (general)
        dense_results = vector_store.search_dense(
            query=query,
            top_k=top_k * 2 if target_page else top_k,
            document_ids=document_ids
        )

        # 2. BM25 keyword retrieval (general)
        bm25_results = bm25_search.search(
            query=query,
            top_k=top_k * 2 if target_page else top_k,
            document_ids=document_ids
        )

        # 3. If a specific page is targeted, also run targeted retrieval for that page
        if target_page is not None:
            targeted_dense = vector_store.search_dense(
                query=query,
                top_k=top_k,
                document_ids=document_ids,
                page_number=target_page
            )
            targeted_bm25 = bm25_search.search(
                query=query,
                top_k=top_k,
                document_ids=document_ids,
                page_number=target_page
            )
            # Combine without duplicate chunk IDs
            seen_ids = {d["chunk_id"] for d in dense_results}
            for td in targeted_dense:
                if td["chunk_id"] not in seen_ids:
                    dense_results.append(td)
                    seen_ids.add(td["chunk_id"])

            seen_bm25 = {b["chunk_id"] for b in bm25_results}
            for tb in targeted_bm25:
                if tb["chunk_id"] not in seen_bm25:
                    bm25_results.append(tb)
                    seen_bm25.add(tb["chunk_id"])

        # If both are empty (no documents indexed yet)
        if not dense_results and not bm25_results:
            return []

        # 4. Reciprocal Rank Fusion with target_page prioritization
        fused = reciprocal_rank_fusion(
            ranked_lists=[dense_results, bm25_results],
            k=settings.RRF_K,
            top_n=top_k,
            target_page=target_page
        )

        # 5. Relevance filtering: avoid returning completely unrelated passages
        # If a passage has very low dense similarity (< 0.22) and zero keyword match, prune it
        filtered = []
        for item in fused:
            dense_score = item.get("score", 0.0) if item.get("source_type") == "dense" else 0.0
            sources = item.get("retrieval_sources", [])
            # Keep if it matched keywords, or dense similarity is above threshold, or it's on target page
            if "bm25" in sources or dense_score >= 0.22 or (target_page and item.get("page") == target_page):
                filtered.append(item)

        return filtered[:top_k]


hybrid_retriever = HybridRetriever()

