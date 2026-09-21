import time
from typing import Optional, List
from google import genai
from google.genai import types
from .base import LLMProvider
from .router import KeyPool, is_rate_limit_error, is_transient_error
from config import settings


class GeminiProvider(LLMProvider):
    """
    Google Gemini Provider dengan dukungan multi-key pool, round-robin, dan failover otomatis.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str | List[str]] = None,
        strategy: str = "round-robin",
    ):
        self.model_name = model or settings.gemini_model or "gemini-2.0-flash"
        keys = api_key or settings.gemini_api_key or ""
        self.key_pool = KeyPool(keys=keys, strategy=strategy)
        print(f"[Gemini] Initialized with model={self.model_name!r}, total_keys={self.key_pool.total_keys}")

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

        max_key_attempts = max(1, self.key_pool.total_keys)
        last_error = None

        for attempt in range(max_key_attempts):
            key_status = await self.key_pool.get_next_key()
            current_key = key_status.key if key_status else settings.gemini_api_key

            t_start = time.time()
            try:
                client = genai.Client(api_key=current_key)
                resp = await client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
                latency = (time.time() - t_start) * 1000
                if key_status:
                    key_status.mark_success(latency_ms=latency)
                return resp.text or ""
            except Exception as e:
                last_error = e
                if is_rate_limit_error(e):
                    if key_status:
                        key_status.mark_rate_limited(cooldown_seconds=60, error_msg=str(e)[:150])
                    print(f"[Gemini] Rate limit 429 on key ...{current_key[-6:] if current_key and len(current_key) > 6 else current_key}. Failover to next key...")
                elif is_transient_error(e) and attempt < max_key_attempts - 1:
                    if key_status:
                        key_status.mark_failed(str(e)[:150], cooldown_seconds=20)
                    print(f"[Gemini] Transient error ({e}). Retrying with next key...")
                else:
                    if key_status:
                        key_status.mark_failed(str(e)[:150])
                    if attempt == max_key_attempts - 1:
                        raise

        if last_error:
            raise last_error
        return ""
