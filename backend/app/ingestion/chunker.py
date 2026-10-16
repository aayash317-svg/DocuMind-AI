from typing import List
from backend.app.ingestion.models import ExtractedDocument, DocumentChunk


class DocumentChunker:
    """Splits document pages into semantically cohesive, overlapping chunks with rich metadata."""

    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 120):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, doc: ExtractedDocument) -> List[DocumentChunk]:
        all_chunks: List[DocumentChunk] = []
        global_chunk_idx = 0

        for page in doc.pages:
            page_text = page.text
            if not page_text:
                continue

            page_chunks = self._split_text(page_text)
            for page_sub_idx, chunk_text in enumerate(page_chunks):
                chunk_id = f"{doc.document_id}_p{page.page_number}_c{page_sub_idx}"
                all_chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        document_id=doc.document_id,
                        filename=doc.filename,
                        page_number=page.page_number,
                        chunk_index=global_chunk_idx,
                        text=chunk_text,
                        metadata={
                            "document_id": doc.document_id,
                            "filename": doc.filename,
                            "page": page.page_number,
                            "chunk_id": chunk_id,
                        }
                    )
                )
                global_chunk_idx += 1

        return all_chunks

    def _split_text(self, text: str) -> List[str]:
        """Split text with overlap on sentence/paragraph boundaries when possible."""
        text = text.strip()
        if len(text) <= self.chunk_size:
            return [text]

        chunks: List[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            
            # If we're not at the very end of the text, try to find a natural break
            if end < text_len:
                # Look for paragraph break or sentence break in the last portion
                window_start = max(start + self.chunk_size // 2, end - 80)
                sub = text[window_start:end]
                
                best_break = -1
                for sep in ["\n\n", "\n", ". ", "? ", "! "]:
                    idx = sub.rfind(sep)
                    if idx != -1:
                        best_break = window_start + idx + len(sep)
                        break

                if best_break != -1 and best_break > start:
                    end = best_break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= text_len:
                break

            # Move start forward by step size (chunk_size - chunk_overlap)
            step = max(self.chunk_size - self.chunk_overlap, 100)
            start += step

        return chunks

