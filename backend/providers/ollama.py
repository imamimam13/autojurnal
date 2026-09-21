import asyncio
import time
import httpx
from typing import Optional, List
from .base import LLMProvider
from .router import EndpointPool, KeyPool
from config import settings


class OllamaProvider(LLMProvider):
    """
    Ollama Provider dengan dukungan multi-host/endpoints dan multi API keys (untuk cloud Ollama).
    """

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str | List[str]] = None,
        api_key: Optional[str | List[str]] = None,
        strategy: str = "round-robin",
    ):
        self.model = model or settings.ollama_model or "gemma3:12b"
        raw_base = base_url or settings.ollama_base_url or "http://localhost:11434"
        self.endpoint_pool = EndpointPool(raw_base)

        raw_keys = api_key or settings.ollama_api_key or ""
        self.key_pool = KeyPool(raw_keys, strategy=strategy)
        print(f"[Ollama] Initialized with endpoints={self.endpoint_pool.endpoints}, model={self.model!r}, total_keys={self.key_pool.total_keys}")

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def display_name(self) -> str:
        return f"Ollama ({self.model})"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # Context sizes to try in order (starts with 32k, falls back if OOM)
        context_sizes = [32768, 16384, 8192]
        retries_per_ctx = 2

        current_endpoint = await self.endpoint_pool.get_next_endpoint()
        key_status = await self.key_pool.get_next_key()
        current_key = key_status.key if key_status else settings.ollama_api_key

        headers = {"Content-Type": "application/json"}
        if current_key:
            headers["Authorization"] = f"Bearer {current_key}"

        url = f"{current_endpoint}/api/generate"

        for ctx_size in context_sizes:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt or "",
                "options": {
                    "temperature": 0.7,
                    "num_predict": 8192,
                    "num_ctx": ctx_size,
                },
                "stream": False,
            }

            client_timeout = httpx.Timeout(timeout=180.0, connect=10.0)
            async with httpx.AsyncClient(timeout=client_timeout, follow_redirects=True) as client:
                for attempt in range(retries_per_ctx):
                    t_start = time.time()
                    try:
                        resp = await client.post(url, json=payload, headers=headers)
                        resp.raise_for_status()
                        data = resp.json()
                        latency = (time.time() - t_start) * 1000
                        if key_status:
                            key_status.mark_success(latency_ms=latency)
                        return data.get("response", "")
                    except httpx.HTTPStatusError as e:
                        err_text = e.response.text[:300]
                        print(f"[Ollama] Attempt {attempt + 1} with num_ctx={ctx_size} failed: {e.response.status_code} - {err_text}")
                        if "out of memory" in err_text.lower() or "cuda" in err_text.lower() or "context" in err_text.lower() or e.response.status_code == 500:
                            print(f"[Ollama] Context/Memory constrained with num_ctx={ctx_size}, falling back to smaller context window...")
                            break
                        if attempt < retries_per_ctx - 1 and e.response.status_code in (429, 502, 503, 504):
                            if e.response.status_code == 429 and key_status:
                                key_status.mark_rate_limited()
                            await asyncio.sleep(2 ** attempt)
                        else:
                            if key_status:
                                key_status.mark_failed(f"HTTP {e.response.status_code}: {err_text[:100]}")
                            raise RuntimeError(f"Ollama HTTP {e.response.status_code} error from {current_endpoint}: {err_text}") from e
                    except httpx.ConnectError as e:
                        print(f"[Ollama] Connection failed to {current_endpoint}: {e}")
                        if key_status:
                            key_status.mark_failed(f"ConnectError: {str(e)[:100]}")
                        raise RuntimeError(f"Tidak dapat terhubung ke Ollama di '{current_endpoint}'. Pastikan Ollama aktif di komputer/server Anda (default: http://localhost:11434).") from e
                    except httpx.TimeoutException as e:
                        print(f"[Ollama] Timeout with num_ctx={ctx_size} (attempt {attempt + 1}): {e}")
                        if attempt < retries_per_ctx - 1:
                            await asyncio.sleep(2 ** attempt)
                        else:
                            if ctx_size == context_sizes[-1]:
                                if key_status:
                                    key_status.mark_failed("Request Timeout (>180s)")
                                raise RuntimeError(f"Ollama request timeout (>180s) pada {current_endpoint}. Model '{self.model}' memerlukan waktu terlalu lama atau endpoint tidak merespons.") from e
                            break
        return ""
