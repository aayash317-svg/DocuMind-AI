from typing import List, Dict, Any, Optional, TypedDict
from langgraph.graph import StateGraph, END

from backend.app.core.config import settings
from backend.app.retrieval.hybrid import hybrid_retriever
from backend.app.generation.llm import ollama_client
from backend.app.generation.citations import citation_validator
from backend.app.generation.models import ChatResponse


class AgentState(TypedDict):
    question: str
    document_ids: Optional[List[str]]
    top_k: int
    retrieved_passages: List[Dict[str, Any]]
    step_count: int
    is_sufficient: bool
    draft_answer: str
    final_response: Optional[ChatResponse]


def retrieve_node(state: AgentState) -> Dict[str, Any]:
    """Retrieve candidate passages using hybrid retrieval (Dense + BM25 + RRF)."""
    question = state["question"]
    top_k = state.get("top_k", settings.RETRIEVAL_TOP_K)
    doc_ids = state.get("document_ids")

    passages = hybrid_retriever.retrieve(
        query=question,
        top_k=top_k,
        document_ids=doc_ids
    )

    return {
        "retrieved_passages": passages,
        "step_count": state.get("step_count", 0) + 1
    }


def evaluate_sufficiency_node(state: AgentState) -> Dict[str, Any]:
    """Evaluate whether retrieved evidence is sufficient to answer."""
    passages = state.get("retrieved_passages", [])
    # If no passages returned, insufficient evidence
    if not passages:
        return {"is_sufficient": False}

    return {"is_sufficient": True}


def sufficiency_router(state: AgentState) -> str:
    """Route based on sufficiency check and bounded step count."""
    if not state.get("is_sufficient", False):
        return "abstain_node"
    return "generate_node"


def abstain_node(state: AgentState) -> Dict[str, Any]:
    """Gracefully abstain when documents provide insufficient evidence."""
    msg = (
        "The provided documents do not contain sufficient evidence to answer this question. "
        "Please upload relevant documents or refine your search query."
    )
    resp = ChatResponse(
        answer=msg,
        insufficient_evidence=True,
        sources=[]
    )
    return {
        "draft_answer": msg,
        "final_response": resp
    }


async def generate_node(state: AgentState) -> Dict[str, Any]:
    """Generate grounded answer strictly based on retrieved passages."""
    question = state["question"]
    passages = state.get("retrieved_passages", [])

    answer = await ollama_client.generate_answer(question, passages)
    return {"draft_answer": answer}


def validate_citations_node(state: AgentState) -> Dict[str, Any]:
    """Validate citations against retrieved passages and produce final structured response."""
    answer = state.get("draft_answer", "")
    passages = state.get("retrieved_passages", [])

    final_resp = citation_validator.build_response(answer, passages)
    return {"final_response": final_resp}


# Build LangGraph StateGraph
builder = StateGraph(AgentState)

builder.add_node("retrieve_node", retrieve_node)
builder.add_node("evaluate_sufficiency_node", evaluate_sufficiency_node)
builder.add_node("abstain_node", abstain_node)
builder.add_node("generate_node", generate_node)
builder.add_node("validate_citations_node", validate_citations_node)

builder.set_entry_point("retrieve_node")
builder.add_edge("retrieve_node", "evaluate_sufficiency_node")
builder.add_conditional_edges(
    "evaluate_sufficiency_node",
    sufficiency_router,
    {
        "generate_node": "generate_node",
        "abstain_node": "abstain_node",
    }
)
builder.add_edge("generate_node", "validate_citations_node")
builder.add_edge("validate_citations_node", END)
builder.add_edge("abstain_node", END)

documind_agent_graph = builder.compile()

