"""Thin, swappable LLM client so agents don't hardcode a provider.

Both providers implement the same tiny interface: `complete(prompt) -> str`.
This is deliberately NOT a general-purpose abstraction (no streaming, no
tool-calling here — LangGraph owns orchestration, this module just needs to
turn a prompt into text) so it stays a five-minute read.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from voltagent.config import settings


class LLMClient(ABC):
    @abstractmethod
    def complete(self, prompt: str, temperature: float = 0.2) -> str:
        ...


class GeminiClient(LLMClient):
    def __init__(self) -> None:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(settings.generation_model)

    def complete(self, prompt: str, temperature: float = 0.2) -> str:
        response = self._model.generate_content(
            prompt, generation_config={"temperature": temperature}
        )
        return response.text or ""


class OpenAIClient(LLMClient):
    def __init__(self) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.openai_api_key)

    def complete(self, prompt: str, temperature: float = 0.2) -> str:
        response = self._client.chat.completions.create(
            model=settings.generation_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Lazy singleton — avoids reconstructing SDK clients on every call, and
    avoids requiring an API key at import time (useful for tests that never
    hit the real LLM)."""
    global _client
    if _client is None:
        if settings.llm_provider == "openai":
            _client = OpenAIClient()
        else:
            _client = GeminiClient()
    return _client
