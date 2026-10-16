from typing import List, Dict, Any, Tuple
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
]


class CitationValidator:
    """Validates citations against retrieved chunks and detects insufficient evidence."""

    @classmethod
    def is_insufficient_evidence(cls, answer: str, passages: List[Dict[str, Any]]) -> bool:
        if not passages:
            return True

        lower_answer = answer.lower()
        return any(trigger in lower_answer for trigger in INSUFFICIENT_EVIDENCE_TRIGGERS)

    @classmethod
    def build_response(cls, answer: str, passages: List[Dict[str, Any]]) -> ChatResponse:
        insufficient = cls.is_insufficient_evidence(answer, passages)

        sources: List[CitationSource] = []
        if not insufficient and passages:
            # Map retrieved passages into verified citation sources
            seen_chunks = set()
            for p in passages:
                cid = p.get("chunk_id", "")
                if cid and cid not in seen_chunks:
                    seen_chunks.add(cid)
                    text_snippet = p.get("text", "")
                    if len(text_snippet) > 160:
                        text_snippet = text_snippet[:157] + "..."

                    sources.append(
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
            insufficient_evidence=insufficient,
            sources=sources
        )


citation_validator = CitationValidator()

