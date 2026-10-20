"""
Unified LLM Client Adapter for OpenAI, Anthropic and Gemini.

Fail-fast by design:
  * A missing provider, API key or model name raises ValueError at construction.
  * There is NO simulated/offline fallback. If a call keeps failing, the error is raised.
  * Transient failures are retried with exponential backoff + jitter (max_retries, default 5),
    then re-raised as RuntimeError.
"""

import time
import random
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import openai
except ImportError:  # only an error if the openai provider is actually selected
    openai = None

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None

SUPPORTED_PROVIDERS = ("openai", "anthropic", "gemini", "ollama")

# Gemini "thinking" models spend output tokens on reasoning; a small cap can truncate the answer.
GEMINI_MIN_OUTPUT_TOKENS = 8192


class LLMClient:
    def __init__(
        self,
        provider: str,
        api_key: Optional[str],
        model: Optional[str],
        max_retries: int = 5,
        base_delay: float = 0.5,
        base_url: Optional[str] = None,
    ):
        self.provider = (provider or "").lower()
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"LLM_PROVIDER must be one of {SUPPORTED_PROVIDERS}, got {provider!r}")
        if not api_key:
            raise ValueError(f"No API key set for LLM provider '{self.provider}' (check .env)")
        if not model:
            raise ValueError(f"No model name set for LLM provider '{self.provider}' (check .env)")

        self.default_model = model
        self.max_retries = max_retries
        self.base_delay = base_delay

        if self.provider in ("openai", "ollama"):
            if openai is None:
                raise ImportError("openai package is required: pip install openai")
            self._openai = openai.OpenAI(api_key=api_key, base_url = base_url)
        elif self.provider == "anthropic":
            if anthropic is None:
                raise ImportError("anthropic package is required: pip install anthropic")
            self._anthropic = anthropic.Anthropic(api_key=api_key)
        else:
            if genai is None:
                raise ImportError("google-genai package is required: pip install google-genai")
            self._gemini = genai.Client(api_key=api_key)

    @classmethod
    def from_settings(cls, s) -> "LLMClient":
        """Build the client from app.config.settings. Single place that maps provider -> key/model."""
        provider = (s.LLM_PROVIDER or "").lower()
        table = {
            "openai": (s.OPENAI_API_KEY, s.OPENAI_MODEL),
            "anthropic": (s.ANTHROPIC_API_KEY, s.ANTHROPIC_MODEL),
            "gemini": (s.GEMINI_API_KEY, s.GEMINI_MODEL),
            "ollama": ("ollama", s.OLLAMA_MODEL),  # Ollama ignores the key; any non-empty string works
        }
        if provider not in table:
            raise ValueError(f"LLM_PROVIDER must be one of {SUPPORTED_PROVIDERS}, got {s.LLM_PROVIDER!r}")
        api_key, model = table[provider]
        return cls(
            provider=provider,
            api_key=api_key,
            model=model,
            max_retries=s.LLM_MAX_RETRIES,
            base_delay=s.LLM_BASE_DELAY_SECONDS,
            base_url=s.OLLAMA_BASE_URL if provider == "ollama" else None,
        )

    def _call_once(self, prompt, system_prompt, model, temperature, max_tokens) -> str:
        if self.provider in ("openai", "ollama"):
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            out_tokens = max(max_tokens, 4096) if self.provider == "ollama" else max_tokens
            resp = self._openai.chat.completions.create(
                model=model, messages=messages, temperature=temperature, max_tokens=out_tokens
            )
            return resp.choices[0].message.content or ""

        if self.provider == "anthropic":
            resp = self._anthropic.messages.create(
                model=model,
                system=system_prompt or "",
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text or ""

        resp = self._gemini.models.generate_content(
            model=model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt or None,
                temperature=temperature,
                max_output_tokens=max(max_tokens, GEMINI_MIN_OUTPUT_TOKENS),
            ),
        )
        text = resp.text
        if not text:
            # Blocked by safety filters or truncated by the token cap: surface it, don't return "".
            raise RuntimeError(f"Gemini returned no text (finish info: {getattr(resp, 'candidates', None)})")
        return text

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        selected_model = model or self.default_model
        last_err: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                return self._call_once(prompt, system_prompt, selected_model, temperature, max_tokens)
            except Exception as e:
                last_err = e
                if attempt == self.max_retries - 1:
                    break
                wait = self.base_delay * (2 ** attempt) + random.uniform(0.1, 0.5)
                logger.warning(
                    f"LLM call attempt {attempt + 1}/{self.max_retries} failed ({e}). Retrying in {wait:.2f}s..."
                )
                time.sleep(wait)

        raise RuntimeError(
            f"LLM call failed after {self.max_retries} attempts ({self.provider}/{selected_model}): {last_err}"
        ) from last_err
