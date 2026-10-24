import pytest
from backend.app.generation.llm import (
    detect_formatting_constraints,
    enforce_formatting,
    ollama_client
)


def test_detect_formatting_constraints_bullets():
    c5 = detect_formatting_constraints("Give me a summary in five bullet points.")
    assert "exactly 5 bullet points" in c5

    c3 = detect_formatting_constraints("Provide 3 bullets explaining the system.")
    assert "exactly 3 bullet points" in c3


def test_detect_formatting_constraints_six_stages():
    c = detect_formatting_constraints("List the six processing stages.")
    assert "all six stages in order" in c
    assert "Audio input" in c


def test_detect_formatting_constraints_one_sentence():
    c = detect_formatting_constraints("Answer in one sentence: what is the initial threshold?")
    assert "EXACTLY one standalone sentence" in c


def test_detect_formatting_constraints_score_090():
    c = detect_formatting_constraints("What does a score of 0.90 prove?")
    assert "NOT proof of fraud" in c


def test_detect_formatting_constraints_measured_accuracy():
    c = detect_formatting_constraints("What is the model's measured accuracy?")
    assert "does not specify the model's measured accuracy" in c


def test_enforce_formatting_bullet_count():
    raw_7_bullets = (
        "- Point 1\n"
        "- Point 2\n"
        "- Point 3\n"
        "- Point 4\n"
        "- Point 5\n"
        "- Point 6\n"
        "- Point 7"
    )
    res = enforce_formatting(raw_7_bullets, "Give me a summary in five bullet points.")
    bullet_lines = [l for l in res.split("\n") if l.strip().startswith("- ")]
    assert len(bullet_lines) == 5
    assert bullet_lines[0] == "- Point 1"
    assert bullet_lines[4] == "- Point 5"


def test_enforce_formatting_single_sentence():
    multi_sent = (
        "The initial synthetic-speech review threshold is 0.75 or higher. "
        "When a clip produces a score at or above this threshold, the clip is flagged for escalation. "
        "[Source: Voice_Shield_Test_Document.txt, Page: 1]"
    )
    res = enforce_formatting(multi_sent, "Answer in one sentence: what is the initial threshold?")
    assert res.startswith("The initial synthetic-speech review threshold is 0.75 or higher.")
    assert "[Source: Voice_Shield_Test_Document.txt, Page: 1]" in res
    assert "When a clip produces" not in res
