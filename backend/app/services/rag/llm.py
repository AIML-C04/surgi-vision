import os
from abc import ABC, abstractmethod


class LLMConfigurationError(ValueError):
    pass


class LLMProviderError(RuntimeError):
    pass

class LLMProvider(ABC):
    @abstractmethod
    def ask(self, query: str, context: str, history: str = "") -> str:
        pass

class MockLLMProvider(LLMProvider):
    def ask(self, query: str, context: str, history: str = "") -> str:
        if query.lower().strip() in ["hi", "hello", "hey"]:
            return "Hello! I am your surgical video assistant. How can I help you?"
        if not context or "No relevant context" in context:
            return "The information is not available in the analyzed video data."
            
        return f"Based on the video knowledge: {context}\n\nAnswer: (Mock generated answer for query: '{query}')"

class HuggingFaceLLMProvider(LLMProvider):
    def __init__(self):
        token = os.getenv("HF_TOKEN")
        if not token:
            raise LLMConfigurationError("HF_TOKEN is not configured")
        
        from huggingface_hub import InferenceClient
        self.client = InferenceClient(token=token)
        self.model = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
        
    def ask(self, query: str, context: str, history: str = "") -> str:
        prompt = f"""SYSTEM:
You are SurgiVision AI, an assistant for analyzing surgical videos.

Answer the user's question using ONLY the supplied video analysis context and conversation history.

Do not invent instruments, detections, timestamps, surgical phases, events, or observations.

Use only evidence records supplied in the context. Return valid JSON only with this shape: {{"answer": "...", "support": "supported|partially_supported|insufficient_evidence", "evidence_ids": ["EVIDENCE_ID"]}}. Cite only exact EVIDENCE_ID values supplied in the context. If evidence is insufficient, say so explicitly and return an empty evidence_ids list. Treat an instrument co-occurrence as simultaneous detection, not instrument interaction. Do not make diagnoses, clinical judgments, or claims about surgical correctness.

If the provided context does not contain enough information to answer, clearly say that the information is not available in the analyzed video data.

When timestamps are available, include them when relevant.

Do not provide a medical diagnosis or claim clinical certainty.

VIDEO CONTEXT:
{context}

CONVERSATION HISTORY:
{history}

USER QUESTION:
{query}

ANSWER:"""

        # We let exceptions bubble up so they can be handled and logged by the caller (chat.py)
        # We do NOT silently swallow errors and return a mock string.
        try:
            response = self.client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=800,
                temperature=0.1,
            )
        except StopIteration as exc:
            raise LLMProviderError(f"The configured Hugging Face model is not available for chat completion: {self.model}") from exc
        content = response.choices[0].message.content or ""
        if not content.strip():
            raise LLMProviderError(f"The configured Hugging Face model returned an empty response: {self.model}")
        return content.strip()

def get_llm_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER", "huggingface").lower()
    
    if provider == "huggingface":
        # Note: exceptions inside HuggingFaceLLMProvider() will bubble up
        # This will properly fail the API request instead of falling back to Mock
        return HuggingFaceLLMProvider()
        
    elif provider == "mock":
        return MockLLMProvider()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}. Must be 'huggingface' or 'mock'.")
