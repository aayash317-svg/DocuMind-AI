import re
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi


class BM25SearchManager:
    """Manages keyword-based BM25 indexing and querying across chunks."""

    def __init__(self):
        self.corpus: List[Dict[str, Any]] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None

    def tokenize(self, text: str) -> List[str]:
        """Simple, robust lowercasing and alphanumeric tokenization."""
        return re.findall(r"\b\w+\b", text.lower())

    def update_corpus(self, chunks: List[Dict[str, Any]]) -> None:
        """Rebuild or sync BM25 index with current chunk collection."""
        self.corpus = chunks
        self.tokenized_corpus = [self.tokenize(c.get("text", "")) for c in chunks]
        if self.tokenized_corpus and any(self.tokenized_corpus):
            self.bm25 = BM25Okapi(self.tokenized_corpus)
        else:
            self.bm25 = None

    def search(
        self,
        query: str,
        top_k: int = 10,
        document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Perform keyword search returning ranked chunks with BM25 scores."""
        if not self.bm25 or not self.corpus:
            return []

        tokens = self.tokenize(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)

        results = []
        for idx, score in enumerate(scores):
            chunk = self.corpus[idx]
            if document_ids and chunk.get("document_id") not in document_ids:
                continue

            if score > 0.0:
                results.append({
                    "chunk_id": chunk.get("chunk_id", ""),
                    "document_id": chunk.get("document_id", ""),
                    "filename": chunk.get("filename", ""),
                    "page": chunk.get("page", 1),
                    "text": chunk.get("text", ""),
                    "score": float(score),
                    "source_type": "bm25"
                })

        # Sort descending by score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


bm25_search = BM25SearchManager()

