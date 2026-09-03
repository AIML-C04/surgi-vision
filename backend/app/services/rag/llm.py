import os
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def ask(self, query: str, context: str) -> str:
        pass

class MockLLMProvider(LLMProvider):
    def ask(self, query: str, context: str) -> str:
        if not context:
            return "NOT AVAILABLE / INSUFFICIENT EVIDENCE"
            
        return f"Based on the video knowledge: {context}\n\nAnswer: (Mock generated answer for query: '{query}')"

class HuggingFaceLLMProvider(LLMProvider):
    def __init__(self):
        token = os.getenv("HF_TOKEN")
        if not token:
            raise ValueError("HF_TOKEN not configured")
        
        from huggingface_hub import InferenceClient
        self.client = InferenceClient(token=token)
        self.model = os.getenv("LLM_MODEL", "mistralai/Mixtral-8x7B-Instruct-v0.1")
        
    def ask(self, query: str, context: str) -> str:
        if not context:
            return "NOT AVAILABLE / INSUFFICIENT EVIDENCE"
            
        prompt = f"""You are a surgical video analysis assistant.
Use ONLY the following context to answer the question.
If the context does not contain the answer, say exactly: NOT AVAILABLE / INSUFFICIENT EVIDENCE.

Context:
{context}

Question: {query}
Answer:"""

        try:
            response = self.client.text_generation(
                prompt,
                model=self.model,
                max_new_tokens=250,
                temperature=0.1
            )
            return response.strip()
        except Exception as e:
            print(f"LLM Error: {e}")
            return "NOT AVAILABLE / INSUFFICIENT EVIDENCE"

def get_llm_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER", "mock")
    if provider == "huggingface":
        try:
            return HuggingFaceLLMProvider()
        except ValueError:
            pass # Fallback to mock if token not provided for local tests
    return MockLLMProvider()
