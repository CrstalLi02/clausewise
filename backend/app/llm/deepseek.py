"""DeepSeek client: primary chat model.

Defaults: base_url=https://api.deepseek.com, model deepseek-v4-flash.
"""
from __future__ import annotations

from app.config import Settings
from app.llm.client import LLMClient


class DeepSeekClient(LLMClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            timeout=settings.deepseek_timeout,
            temperature=settings.deepseek_temperature,
            max_tokens=settings.deepseek_max_tokens,
        )

    def name(self) -> str:
        return "deepseek"
