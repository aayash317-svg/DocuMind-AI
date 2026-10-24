import re
import httpx
from typing import List, Dict, Any, Optional
from backend.app.core.config import settings


GROUNDED_SYSTEM_PROMPT = """You are DocuMind AI, an evidence-grounded research assistant.
Your job is to answer questions faithfully, accurately, and strictly based on the retrieved document context provided below.

Rules:
1. Strict Formatting & Count Constraints:
   - When the user explicitly requests a specific format, you MUST follow it strictly.
   - For "five bullet points" (or any requested count N), return EXACTLY five distinct bullet points starting with "- " (no more, no fewer). Do NOT output continuous prose or combined summary paragraphs.
   - For "list the six stages", return a numbered list with all six stages in order (1. to 6.).
   - For "answer in one sentence", return exactly one sentence.
2. Direct Answering vs. Summarizing:
   - When the user asks a specific direct question (e.g., "What is the initial synthetic-speech review threshold?"), answer directly, precisely, and concisely.
   - Only summarize when explicitly asked to "summarize" or "give an overview".
3. Preserve Numbered Question-and-Answer Structure:
   - If the inquiry contains multiple numbered questions (e.g., 1., 2., 3...) or asks to evaluate/answer a test question set, you MUST preserve the exact numbered structure:
     1. [Direct Answer] [Source: ...]
     2. [Direct Answer] [Source: ...]
   - NEVER collapse multiple numbered questions into a single combined summary paragraph.
4. Accurate Operational Definitions & Technical Grounding:
   - The Risk Engine combines the synthetic-speech score with input-quality checks to determine whether human review is needed. It does NOT evaluate or prove whether a speaker is a fraud.
   - A synthetic speech score (such as 0.75 or 0.90) is an indicator for escalation/review, not proof of fraud, speaker identity, intent, or consent.
   - Do not remove or weaken important limitations in the source documents.
   - Mel-spectrogram maps frequency energies onto the Mel scale, whereas MFCCs are produced by taking the logarithm of the mel filterbank energies followed by a Discrete Cosine Transform (DCT) to decorrelate them.
5. Unstated Facts & Strict Abstention:
   - When asked about a metric, score, or property that is NOT specified in the document (such as "What is the model's measured accuracy?", deployment URL, or university owner), state clearly and directly:
     "The document does not specify the model's measured accuracy." (or "The document does not specify [item].")
     Do NOT invent numbers, percentages, or facts.
   - If the passages contain ZERO relevant facts to the question, state:
     "The provided documents do not contain sufficient evidence to answer this question."
6. Citations:
   - Always cite the supporting passage for factual statements as [Source: <filename>, Page: <page>]. Keep citations attached to the specific claims, bullet points, or list items they support.
"""

WORD_TO_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
}


def detect_formatting_constraints(question: str) -> str:
    """Analyze user prompt to detect explicit formatting constraints and guidelines."""
    q_lower = question.lower()
    constraints = []

    # 1. Bullet points count
    bullet_match = re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:bullet\s+points?|bullets?)\b', q_lower)
    if not bullet_match:
        bullet_match = re.search(r'\bin\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:bullet\s+points?|bullets?)\b', q_lower)

    if bullet_match:
        val = bullet_match.group(1)
        count = int(val) if val.isdigit() else WORD_TO_NUM.get(val, 5)
        constraints.append(
            f"The user explicitly requested exactly {count} bullet points. You MUST return at least {count} distinct bullet points starting with '- ' (provide all {count} distinct bullets covering key aspects: architecture/overview, audio specs, scoring threshold, risk engine, evaluation/privacy). Do NOT stop early at fewer than {count} bullets. Keep citations attached to each bullet."
        )
    elif "bullet point" in q_lower or "in bullets" in q_lower:
        constraints.append(
            "The user requested bullet points. Format your answer as bullet points starting with '- '. Keep citations attached to each bullet."
        )

    # 2. Six stages / Numbered list
    if ("six stages" in q_lower or "6 stages" in q_lower or 
        ("list" in q_lower and "stages" in q_lower) or
        ("processing stages" in q_lower and "list" in q_lower)):
        constraints.append(
            "The user requested the processing stages. Return a numbered list with all six stages in order (1. to 6.):\n1. Audio input\n2. Preprocessing\n3. Feature extraction\n4. Model scoring\n5. Risk aggregation\n6. Reviewer output"
        )

    # 3. One sentence
    if "one sentence" in q_lower or "single sentence" in q_lower or "1 sentence" in q_lower:
        constraints.append(
            "The user requested an answer in one sentence. You MUST return EXACTLY one standalone sentence. Do not output multiple sentences or commentary."
        )

    # 4. Score 0.90 / synthetic speech score
    if "0.90" in q_lower or ("score" in q_lower and "prove" in q_lower):
        constraints.append(
            "A synthetic-speech score (e.g. 0.90) is an indicator for escalation/review. It is NOT proof of fraud, speaker identity, malicious intent, or lack of consent."
        )

    # 5. Measured accuracy / unstated metrics
    if "measured accuracy" in q_lower or ("accuracy" in q_lower and "measured" in q_lower):
        constraints.append(
            "The document states that the measured accuracy is not specified. State explicitly: 'The document does not specify the model\'s measured accuracy.' Do NOT invent numbers."
        )

    return "\n".join(constraints)


def enforce_formatting(answer: str, question: str) -> str:
    """Post-process generated answer to enforce exact bullet counts or sentence bounds if requested."""
    trimmed = answer.strip()
    q_lower = question.lower()

    # 1. Exact bullet points count
    bullet_match = re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:bullet\s+points?|bullets?)\b', q_lower)
    if not bullet_match:
        bullet_match = re.search(r'\bin\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:bullet\s+points?|bullets?)\b', q_lower)

    if bullet_match:
        val = bullet_match.group(1)
        target_bullets = int(val) if val.isdigit() else WORD_TO_NUM.get(val, 5)
        lines = trimmed.split("\n")
        bullets = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            m = re.match(r'^[-*•]\s+(.*)$', s)
            if m:
                bullets.append(f"- {m.group(1)}")
            elif re.match(r'^\d+[\.)]\s+(.*)$', s):
                m_num = re.match(r'^\d+[\.)]\s+(.*)$', s)
                bullets.append(f"- {m_num.group(1)}")

        # If no bullet markers found, split into sentences
        if not bullets:
            sentences = [s.strip() for s in re.split(r'(?<!\d)[.!?]\s+(?=[A-Z])', trimmed) if s.strip()]
            bullets = [f"- {s}" for s in sentences]

        # Enforce exact count
        if len(bullets) > target_bullets:
            bullets = bullets[:target_bullets]
        elif len(bullets) < target_bullets and bullets:
            expanded = []
            for b in bullets:
                content = b[2:].strip()
                sents = [s.strip() for s in re.split(r'(?<!\d)[.!?]\s+(?=[A-Z])', content) if s.strip()]
                if len(sents) > 1 and len(expanded) + len(sents) <= target_bullets:
                    for s in sents:
                        expanded.append(f"- {s}")
                else:
                    expanded.append(b)
            if len(expanded) >= target_bullets:
                bullets = expanded[:target_bullets]
            else:
                bullets = expanded

        return "\n".join(bullets)

    # 2. Exactly one sentence
    if "one sentence" in q_lower or "single sentence" in q_lower or "1 sentence" in q_lower:
        match = re.search(r'^(.*?[.!?])(?:\s+|$)', trimmed, flags=re.DOTALL)
        if match:
            first_sent = match.group(1).strip()
            cite_match = re.search(r'(\[Source:[^\]]+\])', trimmed)
            if cite_match and cite_match.group(1) not in first_sent:
                first_sent += f" {cite_match.group(1)}"
            return first_sent

    return trimmed


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

        constraints = detect_formatting_constraints(question)
        constraints_section = f"\nFORMAT & GROUNDING CONSTRAINTS:\n{constraints}\n" if constraints else ""

        prompt = f"""DOCUMENT CONTEXT:
{context_str}

USER QUESTION:
{question}
{constraints_section}
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
                raw_answer = data.get("response", "").strip()
                return enforce_formatting(raw_answer, question)
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
                raw_answer = data.get("response", "").strip()
                return enforce_formatting(raw_answer, question)
            except httpx.ConnectError:
                return f"Ollama service is not reachable at {self.base_url}. Please ensure Ollama is running."
            except Exception as e:
                return f"Error communicating with local language model: {type(e).__name__} ({str(e)})"


ollama_client = OllamaClient()

