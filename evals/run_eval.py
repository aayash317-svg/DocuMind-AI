import json
import time
import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure project root is in path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.agents.graph import documind_agent_graph
from backend.app.retrieval.hybrid import hybrid_retriever


async def run_evaluation():
    dataset_path = Path(__file__).parent / "datasets" / "sample_eval.json"
    if not dataset_path.exists():
        print(f"Dataset not found at {dataset_path}")
        return

    with open(dataset_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loaded {len(cases)} test cases from {dataset_path.name}")
    results = []
    total_latency = 0.0

    retrieval_hits = 0
    correct_abstentions = 0
    total_abstention_cases = 0

    for case in cases:
        qid = case["id"]
        q = case["question"]
        expected_kws = case.get("expected_answer_keywords", [])
        should_abstain = case.get("should_abstain", False)

        start_time = time.time()
        initial_state = {
            "question": q,
            "document_ids": None,
            "top_k": 5,
            "retrieved_passages": [],
            "step_count": 0,
            "is_sufficient": False,
            "draft_answer": "",
            "final_response": None,
        }

        agent_res = await documind_agent_graph.ainvoke(initial_state)
        latency = time.time() - start_time
        total_latency += latency

        resp = agent_res.get("final_response")
        answer = resp.answer if resp else ""
        insufficient = resp.insufficient_evidence if resp else True
        sources = resp.sources if resp else []

        # Check retrieval hit
        if expected_kws:
            hit = any(kw.lower() in answer.lower() for kw in expected_kws)
            if hit:
                retrieval_hits += 1
        else:
            hit = None

        # Check abstention
        if should_abstain:
            total_abstention_cases += 1
            if insufficient:
                correct_abstentions += 1

        results.append({
            "id": qid,
            "question": q,
            "latency_seconds": round(latency, 2),
            "insufficient_evidence": insufficient,
            "answer_preview": answer[:120] + "..." if len(answer) > 120 else answer,
            "citations_count": len(sources),
            "hit": hit
        })

    avg_latency = total_latency / len(cases) if cases else 0.0
    abstention_accuracy = (correct_abstentions / total_abstention_cases) if total_abstention_cases else 1.0

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report = {
        "timestamp": timestamp,
        "total_cases": len(cases),
        "avg_latency_seconds": round(avg_latency, 2),
        "abstention_accuracy": round(abstention_accuracy, 2),
        "results": results
    }

    report_path = reports_dir / f"eval_report_{timestamp}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n--- Evaluation Completed ---")
    print(f"Report saved to: {report_path}")
    print(f"Average Latency: {avg_latency:.2f}s")
    print(f"Abstention Accuracy: {abstention_accuracy * 100:.1f}%\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_evaluation())

