import time
import asyncio
from typing import Optional, List
from openai import AsyncOpenAI, BadRequestError, RateLimitError, APIError
from .base import LLMProvider
from .router import KeyPool, is_rate_limit_error, is_transient_error
from config import settings


class OpenAICompatibleProvider(LLMProvider):
    """
    Provider generik OpenAI-Compatible berkinerja tinggi.
    Mendukung NVIDIA NIM, DeepSeek, Qwen, Moonshot, Zhipu, Xiaomi MiMo, Groq, OpenRouter, dll.
    Terintegrasi penuh dengan KeyPool multi-key round-robin dan auto-failover.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str | List[str]] = None,
        provider_id: str = "openai_compatible",
        display_title: Optional[str] = None,
        strategy: str = "round-robin",
    ):
        self.provider_id = provider_id
        self.model = model or settings.openai_compatible_model or "llama3"
        self.base_url = (base_url or settings.openai_compatible_base_url or "http://localhost:8080/v1").rstrip("/")
        self._display_title = display_title

        # Inisialisasi KeyPool
        keys = api_key or settings.openai_compatible_api_key or "no-key"
        self.key_pool = KeyPool(keys=keys, strategy=strategy)
        print(f"[{self.display_name}] Initialized with base_url={self.base_url!r}, model={self.model!r}, total_keys={self.key_pool.total_keys}")

    @property
    def name(self) -> str:
        return self.provider_id

    @property
    def display_name(self) -> str:
        if self._display_title:
            return f"{self._display_title} ({self.model})"
        return f"OpenAI Compatible ({self.model})"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Coba eksekusi dengan failover antar API key dalam pool
        max_key_attempts = max(1, self.key_pool.total_keys)
        last_error = None

        for attempt in range(max_key_attempts):
            key_status = await self.key_pool.get_next_key()
            current_key = key_status.key if key_status else "no-key"

            client = AsyncOpenAI(api_key=current_key, base_url=self.base_url, timeout=120.0)
            token_attempts = [4096, 2048]
            t_start = time.time()

            for idx, max_tokens in enumerate(token_attempts):
                try:
                    resp = await client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=max_tokens,
                    )
                    latency = (time.time() - t_start) * 1000
                    if key_status:
                        key_status.mark_success(latency_ms=latency)
                    return resp.choices[0].message.content or ""
                except BadRequestError as e:
                    err_msg = str(e).lower()
                    if ("context" in err_msg or "token" in err_msg or "maximum" in err_msg or "length" in err_msg) and idx < len(token_attempts) - 1:
                        print(f"[{self.name}] Context limit warning, retrying with max_tokens={token_attempts[idx+1]}...")
                        continue
                    last_error = e
                    if key_status:
                        key_status.mark_failed(str(e)[:100])
                    raise
                except RateLimitError as e:
                    last_error = e
                    if key_status:
                        key_status.mark_rate_limited(cooldown_seconds=60, error_msg=str(e)[:150])
                    print(f"[{self.name}] Rate limit 429 on key ...{current_key[-6:] if len(current_key) > 6 else current_key}. Failover to next key...")
                    break  # Break inner loop to try next key
                except Exception as e:
                    last_error = e
                    if is_rate_limit_error(e):
                        if key_status:
                            key_status.mark_rate_limited(cooldown_seconds=60, error_msg=str(e)[:150])
                        print(f"[{self.name}] Quota/RateLimit on key ...{current_key[-6:] if len(current_key) > 6 else current_key}. Switching key...")
                        break
                    elif is_transient_error(e) and attempt < max_key_attempts - 1:
                        if key_status:
                            key_status.mark_failed(str(e)[:150], cooldown_seconds=20)
                        print(f"[{self.name}] Transient error ({e}). Switching to next key/endpoint in pool...")
                        break
                    else:
                        if key_status:
                            key_status.mark_failed(str(e)[:150])
                        if attempt == max_key_attempts - 1:
                            raise
                        break

        if last_error:
            raise last_error
        return ""
