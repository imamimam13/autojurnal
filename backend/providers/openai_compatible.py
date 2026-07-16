from typing import Optional
from openai import AsyncOpenAI
from .base import LLMProvider
from config import settings


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or settings.openai_compatible_model or "llama3"
        self.base_url = base_url or settings.openai_compatible_base_url or "http://localhost:8080/v1"
        self.api_key = api_key or settings.openai_compatible_api_key or "no-key"
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    @property
    def name(self) -> str:
        return "openai_compatible"

    @property
    def display_name(self) -> str:
        return f"OpenAI Compatible ({self.model})"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=8192,
        )
        return resp.choices[0].message.content or ""
