"""Environment-configured LLM client for lightweight JSON-completion calls."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib import error, request


@dataclass(frozen=True)
class LLMConfig:
    """Configuration loaded from environment variables."""

    api_key: str | None
    base_url: str
    model: str
    timeout_s: float
    max_tokens: int

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            timeout_s=float(os.getenv("LLM_TIMEOUT_S", "30")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "200")),
        )


class LLMClient:
    """Tiny client that requests JSON output from a chat-completions style API."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.from_env()

    @property
    def enabled(self) -> bool:
        return bool(self.config.api_key)

    def complete_json(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> dict[str, Any] | None:
        """Return parsed JSON content or None on transport/parsing failure."""
        if not self.enabled:
            return None

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
        }

        url = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        req = request.Request(
            url=url,
            method="POST",
            headers=headers,
            data=json.dumps(payload).encode("utf-8"),
        )
        try:
            with request.urlopen(req, timeout=self.config.timeout_s) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError):
            return None

        try:
            content = body["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content if isinstance(part, Mapping))
            if isinstance(content, str):
                return json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return None

        return None
