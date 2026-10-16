from typing import List, Dict, Any
from backend.app.core.config import settings


def reciprocal_rank_fusion(
    ranked_lists: List[List[Dict[str, Any]]],
    k: int = 60,
    top_n: int = 10
) -> List[Dict[str, Any]]:
    """Combines multiple ranked lists using Reciprocal Rank Fusion (RRF).

    Formula:
        RRF_score(d) = sum_{r in R} (1 / (k + rank_r(d)))
    where rank_r(d) is 1-based index of document d in list r.
    """
    rrf_scores: Dict[str, float] = {}
    doc_lookup: Dict[str, Dict[str, Any]] = {}
    sources_lookup: Dict[str, List[str]] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            chunk_id = item["chunk_id"]
            if not chunk_id:
                continue

            score_contribution = 1.0 / (k + rank)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + score_contribution

            if chunk_id not in doc_lookup:
                doc_lookup[chunk_id] = item
                sources_lookup[chunk_id] = []
            
            source_type = item.get("source_type", "unknown")
            if source_type not in sources_lookup[chunk_id]:
                sources_lookup[chunk_id].append(source_type)

    # Sort chunks by final RRF score in descending order
    sorted_chunk_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

    fused_results = []
    for cid in sorted_chunk_ids[:top_n]:
        base_item = dict(doc_lookup[cid])
        base_item["rrf_score"] = rrf_scores[cid]
        base_item["retrieval_sources"] = sources_lookup[cid]
        fused_results.append(base_item)

    return fused_results

