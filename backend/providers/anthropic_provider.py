from typing import Optional
from anthropic import AsyncAnthropic
from .base import LLMProvider
from config import settings


class AnthropicProvider(LLMProvider):
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or settings.anthropic_model
        self.api_key = api_key or settings.anthropic_api_key
        self.client = AsyncAnthropic(api_key=self.api_key)

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def display_name(self) -> str:
        return f"Anthropic ({self.model})"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = [{"role": "user", "content": prompt}]

        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 32768,
            "temperature": 0.7,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        resp = await self.client.messages.create(**kwargs)
        return resp.content[0].text if resp.content else ""
