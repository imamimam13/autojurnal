from typing import Optional
from .base import LLMProvider
from config import settings


_providers: dict[str, tuple[str, dict]] = {}


def register_provider(name: str, module_path: str, class_name: str, default_kwargs: Optional[dict] = None):
    _providers[name] = (module_path, class_name, default_kwargs or {})


def get_provider(name: str, **kwargs) -> Optional[LLMProvider]:
    entry = _providers.get(name)
    if not entry:
        return None

    module_path, class_name, default_kwargs = entry
    import importlib
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
    except (ImportError, AttributeError):
        return None

    merged_kwargs = {**default_kwargs, **kwargs}
    return cls(**merged_kwargs)


def list_providers() -> list[dict]:
    result = []
    for name in _providers:
        try:
            inst = get_provider(name)
            if inst:
                result.append({"id": name, "name": inst.display_name})
            else:
                result.append({"id": name, "name": name})
        except Exception:
            result.append({"id": name, "name": name})
    return result


register_provider("ollama", "backend.providers.ollama", "OllamaProvider", {"api_key": settings.ollama_api_key})
register_provider("openai", "backend.providers.openai_provider", "OpenAIProvider", {"api_key": settings.openai_api_key})
register_provider("anthropic", "backend.providers.anthropic_provider", "AnthropicProvider", {"api_key": settings.anthropic_api_key})
register_provider("gemini", "backend.providers.gemini_provider", "GeminiProvider", {"api_key": settings.gemini_api_key})
register_provider("openai_compatible", "backend.providers.openai_compatible", "OpenAICompatibleProvider", {
    "api_key": settings.openai_compatible_api_key,
    "base_url": settings.openai_compatible_base_url,
    "model": settings.openai_compatible_model,
})
