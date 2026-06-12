"""OpenAI-compatible LLM client with provider presets and graceful degradation."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str


def is_llm_available() -> bool:
    return settings.llm_enabled


def chat_completion(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> LLMResponse | None:
    """Call configured LLM; return None on missing key or transport/API errors."""
    if not settings.llm_enabled:
        return None

    payload: dict[str, Any] = {
        "model": settings.resolved_llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    url = f"{settings.resolved_llm_base_url.rstrip('/')}/chat/completions"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.llm_request_timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        return LLMResponse(
            content=content,
            model=settings.resolved_llm_model,
            provider=settings.llm_provider,
        )
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning("LLM call failed (%s): %s", settings.llm_provider, exc)
        return None


def truncate_for_llm(text: str, max_chars: int | None = None) -> str:
    """Keep chunk payloads within configured LLM input limits."""
    limit = max_chars if max_chars is not None else settings.llm_max_chunk_chars
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
