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


class FakeLLMClient(LLMClient):
    """Deterministic stand-in for the paid LLM. No network, no randomness.

    It is a test double for the *LLM only*; retrieval, verifier and cache run
    for real. Behaviour is keyed off the prompt text, so the same prompt always
    gives the same output:
      - query reformulation prompt -> echoes the user's query unchanged
      - generation prompt -> quotes the first sentence of source chunk [1]
        with a [1] citation (extractive, so it is "grounded" by construction)
    `scripted` overrides everything: a list of replies (or Exceptions to
    raise) consumed in order, which is how tests inject garbage, empty
    output, timeouts, or a wrong-number answer.
    """

    def __init__(
        self, scripted: list[str | Exception] | None = None, citation_style: str = "after_period"
    ) -> None:
        # Real LLMs use both "sentence. [1]" (after_period) and "sentence [1]." (before_period);
        # the fake supports both so tests exercise each. Default is the original "after_period".
        if citation_style not in ("after_period", "before_period"):
            raise ValueError(f"unknown citation_style: {citation_style}")
        self._citation_style = citation_style
        self._scripted = list(scripted or [])
        self.prompts: list[str] = []   # every prompt seen, for assertions

    def complete(self, prompt: str, temperature: float = 0.2) -> str:
        self.prompts.append(prompt)
        if self._scripted:
            reply = self._scripted.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply

        if "Rewritten query:" in prompt:
            tail = prompt.rsplit("User query (", 1)[-1]
            query_line = tail.split("): ", 1)[-1]
            return query_line.split("\nRewritten query:", 1)[0].strip()

        if "Source chunks:" in prompt:
            block = prompt.split("Source chunks:", 1)[1].split("Technician's question:", 1)[0]
            first = block.strip().split("\n", 2)
            body = first[1].strip() if len(first) > 1 else ""
            sentence = body.split(". ", 1)[0].strip().rstrip(".")
            if not sentence:
                return "I don't have enough information in the available documents to answer that confidently."
            if self._citation_style == "before_period":
                return f"{sentence} [1]."
            return f"{sentence}. [1]"

        return ""


_client: LLMClient | None = None


def set_llm_client(client: LLMClient | None) -> None:
    """Test/chaos hook: install a client (e.g. FakeLLMClient) or reset to lazy default."""
    global _client
    _client = client


def get_llm_client() -> LLMClient:
    """Lazy singleton — avoids reconstructing SDK clients on every call, and
    avoids requiring an API key at import time (useful for tests that never
    hit the real LLM). LLM_PROVIDER=fake selects the deterministic fake."""
    global _client
    if _client is None:
        if settings.llm_provider == "fake":
            _client = FakeLLMClient()
        elif settings.llm_provider == "openai":
            _client = OpenAIClient()
        else:
            _client = GeminiClient()
    return _client
