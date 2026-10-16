import httpx
from typing import List, Dict, Any
from backend.app.core.config import settings


GROUNDED_SYSTEM_PROMPT = """You are DocuMind AI, an evidence-grounded research assistant.
Your job is to answer questions faithfully, accurately, and helpfully based on the retrieved document context provided below.

Rules:
1. Always base factual statements and explanations directly on the provided document passages.
2. When the user asks about a specific page (e.g., "explain page 1" or "on page 4"), thoroughly summarize and explain the content and architecture found on that page. Cite the source passage like [Source: <filename>, Page: <page>].
3. If the user asks an advisory or forward-looking question such as "what we can add", "how to improve", or "recommendations" that is not explicitly detailed in the text:
   - First, thoroughly explain what IS present in the document and cite it.
   - Then, provide sensible, professional engineering recommendations based on the system described, clearly prefacing them: "While the document does not explicitly specify future additions, based on the documented architecture, potential enhancements could include: ..."
4. ONLY if the provided passages contain ZERO relevant facts, concepts, or context to answer the user's question, output:
   "The provided documents do not contain sufficient evidence to answer this question."
5. Be technically precise. Do not confuse related or sequential technical concepts (for instance, note that a Mel-spectrogram maps frequency energies onto the Mel scale, whereas MFCCs are produced by taking the logarithm of the mel filterbank energies followed by a Discrete Cosine Transform (DCT) to decorrelate them). State exact definitions and operational differences from the text.
6. Maintain a structured, professional, and clear tone.
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

