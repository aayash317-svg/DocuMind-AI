import httpx
from typing import List, Dict, Any
from backend.app.core.config import settings


GROUNDED_SYSTEM_PROMPT = """You are DocuMind AI, an evidence-grounded research assistant.
Your job is to answer questions faithfully, accurately, and strictly based on the retrieved document context provided below.

Rules:
1. Direct Answering vs. Summarizing:
   - When the user asks a specific direct question (e.g., "What is the initial synthetic-speech review threshold?"), answer directly, precisely, and concisely.
   - If asked for a specific format (e.g., "Answer in one sentence and cite the exact supporting source"), strictly follow that constraint without adding conversational filler.
   - Only summarize the file when explicitly asked to "summarize" or "give an overview".

2. Preserve Numbered Question-and-Answer Structure:
   - If the inquiry contains multiple numbered questions (e.g., 1., 2., 3...) or asks to evaluate/answer a test question set, you MUST preserve the exact numbered structure:
     1. [Direct Answer] [Source: ...]
     2. [Direct Answer] [Source: ...]
   - NEVER collapse multiple numbered questions into a single combined summary paragraph.

3. Accurate Operational Definitions & Technical Grounding:
   - The Risk Engine combines the synthetic-speech score with input-quality checks to determine whether human review is needed. It does NOT evaluate or prove whether a speaker is a fraud.
   - A synthetic speech score is an indicator for escalation/review, not proof of fraud, identity, intent, or consent.
   - Mel-spectrogram maps frequency energies onto the Mel scale, whereas MFCCs are produced by taking the logarithm of the mel filterbank energies followed by a Discrete Cosine Transform (DCT) to decorrelate them.

4. Unstated Facts & Strict Abstention:
   - When asked about a metric, score, or property that is NOT specified in the document (such as "What is the model's measured accuracy?", deployment URL, or university owner), state clearly and directly:
     "The document does not specify the model's measured accuracy." (or "The document does not specify [item].")
     Do NOT invent numbers, percentages, or facts.
   - If the passages contain ZERO relevant facts to the question, state:
     "The provided documents do not contain sufficient evidence to answer this question."

5. Citations:
   - Always cite the supporting passage for factual statements as [Source: <filename>, Page: <page>].
"""


class OllamaClient:
    """Client for generating grounded answers via local Ollama instance."""

    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL, model: str = settings.OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def build_prompt(self, question: str, passages: List[Dict[str, Any]]) -> str:
        context_parts = []
        for idx, p in enumerate(passages, start=1):
            filename = p.get("filename", "unknown")
            page = p.get("page", 1)
            chunk_id = p.get("chunk_id", f"chunk_{idx}")
            text = p.get("text", "").strip()
            context_parts.append(f"--- Passage {idx} [{filename} | Page {page} | ID: {chunk_id}] ---\n{text}")

        context_str = "\n\n".join(context_parts) if context_parts else "No relevant documents found."
        
        prompt = f"""DOCUMENT CONTEXT:
{context_str}

USER QUESTION:
{question}

GROUNDED ANSWER:"""
        return prompt

    async def generate_answer(self, question: str, passages: List[Dict[str, Any]]) -> str:
        prompt = self.build_prompt(question, passages)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": GROUNDED_SYSTEM_PROMPT,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for strict factual grounding
                "top_p": 0.9,
                "num_predict": 512,
            }
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "").strip()
            except httpx.ConnectError:
                return (
                    "Ollama service is not reachable at "
                    f"{self.base_url}. Please ensure Ollama is running (`ollama serve`)."
                )
            except Exception as e:
                return f"Error communicating with local language model: {type(e).__name__} ({str(e)})"

    def generate_answer_sync(self, question: str, passages: List[Dict[str, Any]]) -> str:
        prompt = self.build_prompt(question, passages)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": GROUNDED_SYSTEM_PROMPT,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 512,
            }
        }

        with httpx.Client(timeout=120.0) as client:
            try:
                response = client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "").strip()
            except httpx.ConnectError:
                return f"Ollama service is not reachable at {self.base_url}. Please ensure Ollama is running."
            except Exception as e:
                return f"Error communicating with local language model: {type(e).__name__} ({str(e)})"


ollama_client = OllamaClient()

