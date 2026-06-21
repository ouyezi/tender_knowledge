from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class EmbeddingResult:
    vector: list[float] | None
    disabled_reason: str | None = None


class EmbeddingClient:
    def __init__(
        self,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str = "default",
    ) -> None:
        self.api_base = (api_base or os.getenv("EMBEDDING_API_BASE", "")).strip()
        self.api_key = (api_key or os.getenv("EMBEDDING_API_KEY", "")).strip()
        self.model = model

    @property
    def is_configured(self) -> bool:
        return bool(self.api_base and self.api_key)

    def embed_text(self, text: str) -> EmbeddingResult:
        if not self.is_configured:
            return EmbeddingResult(vector=None, disabled_reason="embedding_not_configured")
        payload = {"input": text, "model": self.model}
        request = urllib.request.Request(
            f"{self.api_base.rstrip('/')}/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            vector = body["data"][0]["embedding"]
            if not isinstance(vector, list):
                return EmbeddingResult(vector=None, disabled_reason="invalid_embedding_response")
            return EmbeddingResult(vector=[float(item) for item in vector])
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            KeyError,
            IndexError,
            ValueError,
            json.JSONDecodeError,
        ):
            return EmbeddingResult(vector=None, disabled_reason="embedding_request_failed")
