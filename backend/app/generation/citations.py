import re
from typing import List, Dict, Any, Set, Tuple, Optional
from backend.app.generation.models import CitationSource, ChatResponse

INSUFFICIENT_EVIDENCE_TRIGGERS = [
    "insufficient evidence",
    "do not contain sufficient evidence",
    "does not contain sufficient evidence",
    "not enough evidence",
    "not mentioned in the provided",
    "not provided in the documents",
    "documents do not provide",
    "documents do not contain",
    "no relevant information",
    "cannot answer based on the provided",
    "context does not contain",
    "not mentioned in the text",
    "no information provided",
    "no mention of",
    "is not described in the provided",
    "is not found in the documents",
]

STOPWORDS = {
    "the", "and", "is", "in", "to", "of", "it", "that", "this", "for", "with",
    "as", "on", "at", "by", "from", "an", "be", "are", "was", "were", "or",
    "which", "documind", "page", "source", "document", "documents", "provided"
}


class CitationValidator:
    """Validates citations against retrieved chunks, removes unrelated pages, and checks evidence."""

    @classmethod
    def is_insufficient_evidence(cls, answer: str, passages: List[Dict[str, Any]]) -> bool:
        if not passages:
            return True

        trimmed = answer.strip()
        lower_answer = trimmed.lower()

        # Check if the answer begins with or is primarily an explicit abstention
        first_few = lower_answer[:160]
        has_abstention_start = any(
            trigger in first_few for trigger in [
                "do not contain sufficient evidence",
                "does not contain sufficient evidence",
                "insufficient evidence",
                "not enough evidence to answer",
                "no relevant information",
                "cannot answer based on the provided",
                "no information provided to answer",
                "the provided documents do not contain",
            ]
        )
        if has_abstention_start and len(trimmed) < 320:
            return True

        if "provided documents do not contain sufficient evidence" in lower_answer and len(trimmed) < 280:
            return True

        return False

    @classmethod
    def extract_cited_pages(cls, answer: str) -> List[Tuple[Optional[str], Optional[int]]]:
        """Extracts cited filenames and pages from bracketed references in the answer."""
        citations: List[Tuple[Optional[str], Optional[int]]] = []
        
        # Matches: [Source: file.pdf, Page: 4], [file.pdf, Page 4], [file.pdf, p. 4]
        matches = re.findall(
            r"\[(?:Source:?\s*)?([A-Za-z0-9_.\-]+(?:\.[A-Za-z0-9]+))?,?\s*(?:Page|p\.|pg)?\s*(\d+)\]",
            answer,
            re.IGNORECASE
        )
        for fname, page_str in matches:
            page = int(page_str) if page_str else None
            citations.append((fname.strip() if fname else None, page))

        # Matches simple [Page 4] or [p. 4]
        simple_matches = re.findall(r"\[(?:Page|p\.|pg)?\s*(\d+)\]", answer, re.IGNORECASE)
        for page_str in simple_matches:
            citations.append((None, int(page_str)))

        return citations

    @classmethod
    def _extract_content_words(cls, text: str) -> Set[str]:
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        return {w for w in words if w not in STOPWORDS}

    @classmethod
    def build_response(cls, answer: str, passages: List[Dict[str, Any]]) -> ChatResponse:
        insufficient = cls.is_insufficient_evidence(answer, passages)

        if insufficient or not passages:
            return ChatResponse(
                answer=answer,
                insufficient_evidence=True,
                sources=[]
            )

        cited_refs = cls.extract_cited_pages(answer)
        answer_words = cls._extract_content_words(answer)

        verified_sources: List[CitationSource] = []
        seen_chunks = set()

        # Score and filter passages based on actual citation match and content overlap
        scored_passages = []
        for p in passages:
            cid = p.get("chunk_id", "")
            if not cid or cid in seen_chunks:
                continue

            page = int(p.get("page", 1))
            filename = p.get("filename", "")
            chunk_text = p.get("text", "")
            chunk_words = cls._extract_content_words(chunk_text)

            # 1. Did the answer explicitly cite this page or file?
            is_explicitly_cited = False
            for c_fname, c_page in cited_refs:
                if c_page == page and (not c_fname or c_fname.lower() in filename.lower()):
                    is_explicitly_cited = True
                    break

            # 2. Content word overlap
            overlap = len(answer_words.intersection(chunk_words))

            # Only retain passages that are either explicitly cited OR have high content support
            if is_explicitly_cited or overlap >= 4:
                relevance_score = (100 if is_explicitly_cited else 0) + overlap
                scored_passages.append((relevance_score, p))
                seen_chunks.add(cid)

        # Sort verified passages by relevance score (highest first)
        scored_passages.sort(key=lambda x: x[0], reverse=True)

        # Fallback: if no passage had explicit citation or high overlap, take top-1 retrieved chunk
        if not scored_passages and passages:
            scored_passages.append((1, passages[0]))

        for _, p in scored_passages[:5]:
            cid = p.get("chunk_id", "")
            text_snippet = p.get("text", "").strip()
            if len(text_snippet) > 180:
                text_snippet = text_snippet[:177] + "..."

            verified_sources.append(
                CitationSource(
                    document_id=p.get("document_id", ""),
                    filename=p.get("filename", ""),
                    page=int(p.get("page", 1)),
                    chunk_id=cid,
                    snippet=text_snippet
                )
            )

        return ChatResponse(
            answer=answer,
            insufficient_evidence=False,
            sources=verified_sources
        )


citation_validator = CitationValidator()
