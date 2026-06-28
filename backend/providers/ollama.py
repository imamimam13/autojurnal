import asyncio
import httpx
from typing import Optional
from .base import LLMProvider
from config import settings


class OllamaProvider(LLMProvider):
    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or settings.ollama_model
        base = base_url or settings.ollama_base_url
        self.base_url = base.rstrip("/")
        self.api_key = api_key or settings.ollama_api_key
        print(f"[Ollama] Initialized with base_url={self.base_url!r}, model={self.model!r}, api_key={'***' if self.api_key else None}")

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def display_name(self) -> str:
        return f"Ollama ({self.model})"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt or "",
            "options": {"temperature": 0.7, "num_predict": 8192},
            "stream": False,
        }
        retries = 3
        url = f"{self.base_url}/api/generate"
        print(f"[Ollama] POST {url}  model={self.model!r}")
        async with httpx.AsyncClient(timeout=120) as client:
            for attempt in range(retries):
                try:
                    resp = await client.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return data.get("response", "")
                except httpx.HTTPStatusError as e:
                    print(f"[Ollama] Attempt {attempt + 1}/{retries} failed: {e.response.status_code} - {e.response.text[:200]}")
                    if attempt < retries - 1 and e.response.status_code in (429, 500, 502, 503, 504):
                        await asyncio.sleep(2 ** attempt)
                    else:
                        raise
                except (httpx.ConnectError, httpx.TimeoutException) as e:
                    print(f"[Ollama] Connection failed (attempt {attempt + 1}/{retries}): {e}")
                    if attempt < retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        raise
        return ""
