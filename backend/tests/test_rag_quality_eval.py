import pytest
from pathlib import Path
from backend.app.ingestion.extractor import DocumentExtractor
from backend.app.ingestion.chunker import DocumentChunker
from backend.app.retrieval.bm25_search import BM25SearchManager
from backend.app.retrieval.rrf import reciprocal_rank_fusion
from backend.app.generation.citations import citation_validator
from backend.app.generation.llm import detect_formatting_constraints, enforce_formatting


@pytest.fixture(scope="module")
def voice_shield_document():
    doc_path = Path("data/sample_docs/Voice_Shield_Test_Document.txt")
    if not doc_path.exists():
        pytest.skip(f"Test document not found at {doc_path}")
    extracted = DocumentExtractor.extract(doc_path, "doc_voice_shield", "Voice_Shield_Test_Document.txt")
    chunker = DocumentChunker(chunk_size=400, chunk_overlap=80)
    chunks = chunker.chunk_document(extracted)
    return extracted, chunks


def test_eval_initial_synthetic_speech_review_threshold(voice_shield_document):
    """Q1: What is the initial synthetic-speech review threshold? Answer in one sentence and cite the exact supporting source."""
    extracted, chunks = voice_shield_document
    bm = BM25SearchManager()
    bm.update_corpus([c.model_dump() for c in chunks])

    results = bm.search("initial synthetic-speech review threshold", top_k=3)
    assert len(results) >= 1
    assert any("0.75" in r["text"] for r in results)

    # Validate constraint detection
    prompt = "What is the initial synthetic-speech review threshold? Answer in one sentence and cite the exact supporting source."
    constraint = detect_formatting_constraints(prompt)
    assert "one standalone sentence" in constraint

    # Verify citation validator
    answer = "The initial synthetic-speech review threshold is 0.75 or higher [Source: Voice_Shield_Test_Document.txt, Page: 1]."
    validated = citation_validator.build_response(answer, results)
    assert validated.insufficient_evidence is False
    assert len(validated.sources) >= 1
    assert validated.sources[0].filename == "Voice_Shield_Test_Document.txt"
    assert validated.sources[0].page == 1


def test_eval_measured_accuracy_unspecified_behavior(voice_shield_document):
    """Q2: What is the model's measured accuracy?

    Expected behavior: The document does not specify the model's measured accuracy.
    No percentage should be hallucinated, and no false citations should be attached.
    """
    extracted, chunks = voice_shield_document
    bm = BM25SearchManager()
    bm.update_corpus([c.model_dump() for c in chunks])

    results = bm.search("measured accuracy", top_k=3)
    assert len(results) >= 1

    # Verify formatting constraint detects unstated fact guideline
    constraint = detect_formatting_constraints("What is the model's measured accuracy?")
    assert "does not specify the model's measured accuracy" in constraint

    # Verify citation validator accurately links the explicit limitation note when present
    answer = "The document does not specify the model's measured accuracy."
    validated = citation_validator.build_response(answer, results)
    assert len(validated.sources) >= 1
    assert any(term in validated.sources[0].snippet.lower() for term in ["not specified", "does not specify"])

    # Verify that when passages contain ZERO relevant facts, fallback is never fabricated
    unrelated_passages = [{"chunk_id": "c99", "filename": "audio.wav", "page": 1, "text": "Raw audio input 16 kHz."}]
    validated_unrelated = citation_validator.build_response("The document does not specify the university owner.", unrelated_passages)
    assert len(validated_unrelated.sources) == 0


def test_eval_six_stages_ordered_list(voice_shield_document):
    """Q3: List the six processing stages."""
    extracted, chunks = voice_shield_document
    bm = BM25SearchManager()
    bm.update_corpus([c.model_dump() for c in chunks])

    results = bm.search("six processing stages Audio input Preprocessing", top_k=3)
    assert any("Audio input" in r["text"] for r in results)

    constraint = detect_formatting_constraints("List the six processing stages.")
    assert "all six stages in order" in constraint
    assert "Reviewer output" in constraint


def test_eval_five_bullet_points_constraint():
    """Q4: Verify five-bullet summary covering requested topics and key limitations."""
    question = "Give me a summary in five bullet points."
    c = detect_formatting_constraints(question)
    assert "exactly 5 bullet points" in c
    assert "Purpose & Audio Specifications" in c
    assert "Six Processing Stages" in c
    assert "Review Threshold & Risk Engine" in c
    assert "Evaluation Benchmark" in c
    assert "Key Limitations" in c
    assert "held-out data" in c

    sample_five_bullets = (
        "- Voice Shield assesses synthetic speech in 16 kHz or 44.1 kHz WAV files up to 30 seconds [Source: Voice_Shield_Test_Document.txt, Page: 1].\n"
        "- The pipeline comprises six stages: audio input, preprocessing, feature extraction, model scoring, risk aggregation, and reviewer output [Source: Voice_Shield_Test_Document.txt, Page: 1].\n"
        "- The initial synthetic-speech review threshold is 0.75 or higher, serving as an operational decision aid [Source: Voice_Shield_Test_Document.txt, Page: 1].\n"
        "- The sample evaluation dataset contains 1,200 audio clips (600 genuine, 600 synthetic) tracking precision, recall, FPR, FNR, and ROC-AUC [Source: Voice_Shield_Test_Document.txt, Page: 1].\n"
        "- The score alone does not prove fraud, identity, intent, or consent; the model may make errors, and the threshold requires validation on held-out data [Source: Voice_Shield_Test_Document.txt, Page: 1]."
    )
    formatted = enforce_formatting(sample_five_bullets, question)
    bullet_items = [line for line in formatted.split("\n") if line.strip().startswith("- ")]
    assert len(bullet_items) == 5
    assert "held-out data" in bullet_items[4]
    assert "not prove fraud" in bullet_items[4]


def test_eval_citations_supporting_limitations_and_threshold(voice_shield_document):
    """Verify citations accurately link and support threshold and limitation claims."""
    extracted, chunks = voice_shield_document
    bm = BM25SearchManager()
    bm.update_corpus([c.model_dump() for c in chunks])

    # 1. Threshold claim and held-out validation citation
    thresh_results = bm.search("initial review threshold 0.75 held-out data operational", top_k=3)
    assert len(thresh_results) >= 1
    target_thresh_page = thresh_results[0].get("page", 2)
    thresh_answer = f"The initial review threshold of 0.75 must be validated on held-out data before operational use [Source: Voice_Shield_Test_Document.txt, Page: {target_thresh_page}]."
    thresh_resp = citation_validator.build_response(thresh_answer, thresh_results)
    assert thresh_resp.insufficient_evidence is False
    assert len(thresh_resp.sources) >= 1
    assert thresh_resp.sources[0].filename == "Voice_Shield_Test_Document.txt"
    assert thresh_resp.sources[0].page == target_thresh_page
    assert any(term in thresh_resp.sources[0].snippet for term in ["0.75", "held-out", "threshold"])

    # 2. Key limitation: score not proof of fraud/identity/intent/consent, model may make errors
    limit_results = bm.search("model may make errors score not proof fraud identity intent consent", top_k=3)
    assert len(limit_results) >= 1
    target_limit_page = limit_results[0].get("page", 2)
    limit_answer = f"The model may make errors and the score alone is not proof of fraud, speaker identity, intent, or consent [Source: Voice_Shield_Test_Document.txt, Page: {target_limit_page}]."
    limit_resp = citation_validator.build_response(limit_answer, limit_results)
    assert limit_resp.insufficient_evidence is False
    assert len(limit_resp.sources) >= 1
    assert limit_resp.sources[0].filename == "Voice_Shield_Test_Document.txt"
    assert "not proof of fraud" in limit_resp.sources[0].snippet or "errors" in limit_resp.sources[0].snippet


def test_eval_summary_avoids_replacing_content_with_missing_details():
    """Verify that general summary requests prioritize affirmative content and avoid missing details dump."""
    c = detect_formatting_constraints("Give me the details about this TXT file.")
    assert "DOCUMENT SUMMARY GUIDELINES" in c
    assert "Do NOT substitute relevant document content with a list of unspecified or missing details" in c
    assert "Six-stage workflow" in c
    assert "held-out data" in c
    assert "not prove fraud" in c


def test_eval_score_090_not_proof_of_fraud():
    """Q5: What does a score of 0.90 prove?

    Must not claim it proves identity, fraud, intent, or consent.
    """
    constraint = detect_formatting_constraints("What does a score of 0.90 prove?")
    assert "NOT proof of fraud" in constraint
    assert "indicator for escalation/review" in constraint


def test_eval_risk_engine_role(voice_shield_document):
    """Q6: What are the Risk Engine responsibilities and scope?"""
    extracted, chunks = voice_shield_document
    bm = BM25SearchManager()
    bm.update_corpus([c.model_dump() for c in chunks])

    results = bm.search("Risk Engine applies the review threshold and considers input-quality warnings", top_k=3)
    matching = [r for r in results if "Risk Engine" in r["text"] and "review threshold" in r["text"]]
    assert len(matching) >= 1

    results_agg = bm.search("risk aggregation stage combines model score with input-quality checks", top_k=3)
    matching_agg = [r for r in results_agg if "combines the model score with input-quality checks" in r["text"]]
    assert len(matching_agg) >= 1
