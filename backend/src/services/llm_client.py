"""OpenAI-compatible LLM client with provider presets and graceful degradation."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
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


def _open_request(request: urllib.request.Request, *, timeout_sec: int):
    host = urllib.parse.urlparse(request.full_url).hostname or ""
    if host.endswith("dashscope.aliyuncs.com"):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(request, timeout=timeout_sec)
    return urllib.request.urlopen(request, timeout=timeout_sec)


def chat_completion(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    timeout_sec: int | None = None,
    model: str | None = None,
    enable_thinking: bool | None = None,
) -> LLMResponse | None:
    """Call configured LLM; return None on missing key or transport/API errors."""
    if not settings.llm_enabled:
        return None

    resolved_model = model or settings.resolved_llm_model
    payload: dict[str, Any] = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if enable_thinking is not None:
        payload["enable_thinking"] = enable_thinking
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
        with _open_request(
            request,
            timeout_sec=timeout_sec if timeout_sec is not None else settings.llm_request_timeout_sec,
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        return LLMResponse(
            content=content,
            model=resolved_model,
            provider=settings.llm_provider,
        )
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        OSError,
        KeyError,
        IndexError,
        json.JSONDecodeError,
    ) as exc:
        logger.warning("LLM call failed (%s): %s", settings.llm_provider, exc)
        return None


def truncate_for_llm(text: str, max_chars: int | None = None) -> str:
    """Keep chunk payloads within configured LLM input limits."""
    limit = max_chars if max_chars is not None else settings.llm_max_chunk_chars
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
