import asyncio
from typing import Optional
from ollama import AsyncClient, ResponseError
from .base import LLMProvider
from config import settings


class OllamaProvider(LLMProvider):
    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or settings.ollama_model
        base = base_url or settings.ollama_base_url
        self.base_url = base.rstrip("/")
        self.client = AsyncClient(host=self.base_url)
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def display_name(self) -> str:
        return f"Ollama ({self.model})"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        options = {"temperature": 0.7, "num_predict": 8192}
        retries = 3
        for attempt in range(retries):
            try:
                resp = await self.client.generate(
                    model=self.model,
                    prompt=prompt,
                    system=system_prompt or "",
                    options=options,
                )
                return resp.get("response", "")
            except ResponseError as e:
                print(f"[Ollama] Attempt {attempt + 1}/{retries} failed: {e.status_code} - {e.error}")
                if attempt < retries - 1 and e.status_code in (429, 500, 502, 503, 504):
                    wait = 2 ** attempt
                    print(f"[Ollama] Retrying in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    raise
            except (ConnectionError, ConnectionRefusedError, OSError) as e:
                print(f"[Ollama] Connection failed (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    wait = 2 ** attempt
                    print(f"[Ollama] Retrying in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    raise
