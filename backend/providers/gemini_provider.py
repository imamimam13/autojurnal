from typing import Optional
from google import genai
from google.genai import types
from .base import LLMProvider
from config import settings


class GeminiProvider(LLMProvider):
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model_name = model or settings.gemini_model
        self.api_key = api_key or settings.gemini_api_key
        self.client = genai.Client(api_key=self.api_key)

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return f"Google Gemini ({self.model_name})"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        config = types.GenerateContentConfig(temperature=0.7, max_output_tokens=65536)
        if system_prompt:
            config.system_instruction = system_prompt

        resp = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        return resp.text or ""

