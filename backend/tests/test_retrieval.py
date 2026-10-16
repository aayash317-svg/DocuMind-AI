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

