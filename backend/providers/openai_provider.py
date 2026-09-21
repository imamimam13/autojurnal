import time
from typing import Optional, List
from openai import AsyncOpenAI
from .base import LLMProvider
from .router import KeyPool, is_rate_limit_error, is_transient_error
from config import settings


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str | List[str]] = None,
        base_url: Optional[str] = None,
        strategy: str = "round-robin",
    ):
        self.model = model or settings.openai_model or "gpt-4o-mini"
        self.base_url = base_url or "https://api.openai.com/v1"
        keys = api_key or settings.openai_api_key or ""
        self.key_pool = KeyPool(keys=keys, strategy=strategy)
        print(f"[OpenAI] Initialized with model={self.model!r}, total_keys={self.key_pool.total_keys}")

    @property
    def name(self) -> str:
        return "openai"

    @property
    def display_name(self) -> str:
        return f"OpenAI ({self.model})"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        max_key_attempts = max(1, self.key_pool.total_keys)
        last_error = None

        for attempt in range(max_key_attempts):
            key_status = await self.key_pool.get_next_key()
            current_key = key_status.key if key_status else settings.openai_api_key

            t_start = time.time()
            try:
                client = AsyncOpenAI(api_key=current_key, base_url=self.base_url)
                resp = await client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=32768,
                )
                latency = (time.time() - t_start) * 1000
                if key_status:
                    key_status.mark_success(latency_ms=latency)
                return resp.choices[0].message.content or ""
            except Exception as e:
                last_error = e
                if is_rate_limit_error(e):
                    if key_status:
                        key_status.mark_rate_limited(cooldown_seconds=60, error_msg=str(e)[:150])
                    print(f"[OpenAI] Rate limit 429 on key ...{current_key[-6:] if current_key and len(current_key) > 6 else current_key}. Failover to next key...")
                elif is_transient_error(e) and attempt < max_key_attempts - 1:
                    if key_status:
                        key_status.mark_failed(str(e)[:150], cooldown_seconds=20)
                    print(f"[OpenAI] Transient error ({e}). Retrying with next key...")
                else:
                    if key_status:
                        key_status.mark_failed(str(e)[:150])
                    if attempt == max_key_attempts - 1:
                        raise

        if last_error:
            raise last_error
        return ""
