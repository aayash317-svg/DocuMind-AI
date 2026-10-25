from backend.app.retrieval.rrf import reciprocal_rank_fusion
from backend.app.generation.citations import citation_validator


def test_reciprocal_rank_fusion():
    list1 = [
        {"chunk_id": "c1", "text": "passage 1", "source_type": "dense"},
        {"chunk_id": "c2", "text": "passage 2", "source_type": "dense"},
    ]
    list2 = [
        {"chunk_id": "c2", "text": "passage 2", "source_type": "bm25"},
        {"chunk_id": "c3", "text": "passage 3", "source_type": "bm25"},
    ]

    fused = reciprocal_rank_fusion([list1, list2], k=60, top_n=3)
    assert len(fused) == 3
    # c2 was present in both lists (dense rank 2, bm25 rank 1), so it should rank first:
    # c2 score = (1 / (60 + 2)) + (1 / (60 + 1)) = ~0.0161 + ~0.0164 = 0.0325
    # c1 score = 1 / (60 + 1) = 0.0164
    assert fused[0]["chunk_id"] == "c2"
    assert "dense" in fused[0]["retrieval_sources"]
    assert "bm25" in fused[0]["retrieval_sources"]


def test_citation_validator_insufficient_evidence():
    answer_insufficient = "The provided documents do not contain sufficient evidence to answer this question."
    passages = [{"chunk_id": "c1", "filename": "sample.pdf", "page": 1, "text": "Some text"}]
    
    resp = citation_validator.build_response(answer_insufficient, passages)
    assert resp.insufficient_evidence is True
    assert len(resp.sources) == 0


def test_citation_validator_grounded_response():
    answer_valid = "Antigravity is designed by Google Deepmind [Source: test.pdf, Page: 2]."
    passages = [{
        "chunk_id": "c10",
        "document_id": "doc_10",
        "filename": "test.pdf",
        "page": 2,
        "text": "Antigravity is designed by Google Deepmind."
    }]
    
    resp = citation_validator.build_response(answer_valid, passages)
    assert resp.insufficient_evidence is False
    assert len(resp.sources) == 1
    assert resp.sources[0].filename == "test.pdf"
    assert resp.sources[0].page == 2


def test_reciprocal_rank_fusion_target_page_boost():
    """Verify that chunks on the targeted page receive priority."""
    list1 = [
        {"chunk_id": "c1", "page": 2, "chunk_index": 0, "text": "Page 2 content", "source_type": "dense"},
        {"chunk_id": "c2", "page": 1, "chunk_index": 0, "text": "Page 1 intro", "source_type": "dense"},
    ]
    # Without target_page, c1 is rank 1
    fused_default = reciprocal_rank_fusion([list1], k=60, top_n=2)
    assert fused_default[0]["chunk_id"] == "c1"

    # With target_page=1, c2 receives the boost and ranks first
    fused_boosted = reciprocal_rank_fusion([list1], k=60, top_n=2, target_page=1)
    assert fused_boosted[0]["chunk_id"] == "c2"


def test_citation_validator_substantive_with_caveat():
    """Verify that long substantive answers explaining a page are NOT flagged as insufficient evidence."""
    substantive_answer = (
        "Page 1 describes the high-level architecture of DocuMind AI, which is a local-first RAG assistant "
        "supporting PDF, DOCX, and TXT files with persistent vector storage [Source: arch.md, Page: 1]. "
        "While future additions are not explicitly listed in the text, recommended enhancements include "
        "adding multi-modal support and advanced semantic caching."
    )
    passages = [{
        "chunk_id": "c1",
        "document_id": "doc_1",
        "filename": "arch.md",
        "page": 1,
        "text": "DocuMind AI is a local-first RAG assistant supporting PDF, DOCX, and TXT files with vector storage."
    }]

    resp = citation_validator.build_response(substantive_answer, passages)
    assert resp.insufficient_evidence is False
    assert len(resp.sources) >= 1
    assert resp.sources[0].page == 1


def test_citation_validator_unspecified_metric_no_fallback_citation():
    """Verify that when the document is silent on a metric, no fabricated citation is attached."""
    unspecified_answer = "The document does not specify the model's measured accuracy."
    passages = [{
        "chunk_id": "c1",
        "document_id": "doc_voice",
        "filename": "Voice_Shield_Test_Document.txt",
        "page": 1,
        "text": "The Risk Engine evaluates synthetic speech with a threshold of 0.75."
    }]

    resp = citation_validator.build_response(unspecified_answer, passages)
    assert len(resp.sources) == 0


def test_bm25_search_scoring_and_filtering():
    """Verify BM25 search ranking, page number preservation, and document isolation."""
    from backend.app.retrieval.bm25_search import BM25SearchManager

    bm = BM25SearchManager()
    chunks = [
        {"chunk_id": "c1", "document_id": "d1", "filename": "audio.txt", "page": 1, "text": "Mel-spectrogram maps frequency energies onto the Mel scale."},
        {"chunk_id": "c2", "document_id": "d1", "filename": "audio.txt", "page": 2, "text": "Discrete Cosine Transform decorrelates filterbank coefficients to produce MFCCs."},
        {"chunk_id": "c3", "document_id": "d2", "filename": "other.txt", "page": 1, "text": "Unrelated database indexing notes."}
    ]
    bm.update_corpus(chunks)

    results = bm.search("Discrete Cosine Transform MFCCs", top_k=2)
    assert len(results) >= 1
    assert results[0]["chunk_id"] == "c2"
    assert results[0]["page"] == 2

    # Verify document_id filtering
    isolated = bm.search("Discrete Cosine Transform", top_k=5, document_ids=["d2"])
    assert len(isolated) == 0


def test_hybrid_target_page_detection():
    """Verify extraction of target page numbers from user query strings."""
    from backend.app.retrieval.hybrid import HybridRetriever

    assert HybridRetriever.extract_target_page("What is on page 4?") == 4
    assert HybridRetriever.extract_target_page("Summarize pg. 2 please.") == 2
    assert HybridRetriever.extract_target_page("According to p 12, what is the rule?") == 12
    assert HybridRetriever.extract_target_page("Explain synthetic speech risk score.") is None


