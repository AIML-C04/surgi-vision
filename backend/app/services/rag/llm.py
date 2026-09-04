import os
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def ask(self, query: str, context: str) -> str:
        pass

class MockLLMProvider(LLMProvider):
    def ask(self, query: str, context: str) -> str:
        if query.lower().strip() in ["hi", "hello", "hey"]:
            return "Hello! I am your surgical video assistant. How can I help you?"
        if not context:
            return "Insufficient evidence in this video."
            
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
        prompt = f"""You are a surgical video analysis assistant.
If the user says hello or greets you, respond naturally and offer to help analyze the video.
For questions about the video, use ONLY the following context to answer the question.
If the context does not contain the answer to a video-specific question, say exactly: Insufficient evidence in this video.
If the user asks about the surgical phase or phase recognition, say exactly: Phase recognition is currently unavailable because no validated phase recognition model is loaded.

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
    provider = os.getenv("LLM_PROVIDER", "huggingface")
    if provider == "huggingface":
        try:
            return HuggingFaceLLMProvider()
        except ValueError as e:
            raise RuntimeError(f"Hugging Face configuration error: {e}")
    elif provider == "mock":
        return MockLLMProvider()
    else:
        raise RuntimeError(f"Unknown LLM_PROVIDER: {provider}")
