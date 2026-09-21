import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from .base import LLMProvider
from .catalog import AI_CATALOG, get_catalog_entry
from config import settings

_providers: Dict[str, tuple[str, str, dict]] = {}

SETTINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "ai_settings.json"


def load_user_ai_settings() -> Dict[str, Any]:
    """Memuat konfigurasi provider yang disimpan user di JSON."""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Factory] Failed to read ai_settings.json: {e}")
        return {}


def save_user_ai_settings(data: Dict[str, Any]):
    """Menyimpan konfigurasi provider ke file JSON."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = SETTINGS_FILE.with_suffix(".tmp")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp_file.replace(SETTINGS_FILE)
    print(f"[Factory] Saved custom AI settings to {SETTINGS_FILE}")


def register_provider(name: str, module_path: str, class_name: str, default_kwargs: Optional[dict] = None):
    _providers[name] = (module_path, class_name, default_kwargs or {})


def get_provider(name: str, **kwargs) -> Optional[LLMProvider]:
    """
    Mengembalikan instance LLMProvider berdasarkan nama / ID.
    Mengecek:
    1. Preset yang terdaftar di _providers
    2. Preset di AI_CATALOG (OpenAI Compatible presets seperti NVIDIA, DeepSeek, Qwen, Xiaomi MiMo, dll.)
    3. Custom config di ai_settings.json
    """
    user_settings = load_user_ai_settings()
    provider_config = user_settings.get(name, {})

    # Gabungkan prioritas kwargs: argument function > user saved settings > catalog default
    merged_kwargs = {**provider_config, **kwargs}

    # 1. Cek explicit registered provider
    if name in _providers:
        module_path, class_name, default_kwargs = _providers[name]
        import importlib
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            final_kwargs = {**default_kwargs, **merged_kwargs}
            return cls(**final_kwargs)
        except (ImportError, AttributeError) as e:
            print(f"[Factory] Error loading registered provider '{name}': {e}")
            return None

    # 2. Cek apakah ada di AI_CATALOG
    catalog_entry = get_catalog_entry(name)
    if catalog_entry:
        cat_type = catalog_entry.get("type", "openai_compatible")
        if cat_type == "openai_compatible":
            from .openai_compatible import OpenAICompatibleProvider
            base_url = merged_kwargs.get("base_url") or catalog_entry.get("default_base_url")
            model = merged_kwargs.get("model") or catalog_entry.get("default_model")
            api_key = merged_kwargs.get("api_key")
            
            # Cek environment variable jika api_key belum ada
            if not api_key:
                env_name = catalog_entry.get("key_env", "")
                if env_name:
                    api_key = getattr(settings, env_name.lower(), None)

            return OpenAICompatibleProvider(
                model=model,
                base_url=base_url,
                api_key=api_key,
                provider_id=name,
                display_title=catalog_entry.get("name")
            )
        elif cat_type == "gemini":
            from .gemini_provider import GeminiProvider
            return GeminiProvider(
                model=merged_kwargs.get("model") or catalog_entry.get("default_model"),
                api_key=merged_kwargs.get("api_key") or settings.gemini_api_key
            )
        elif cat_type == "openai":
            from .openai_provider import OpenAIProvider
            return OpenAIProvider(
                model=merged_kwargs.get("model") or catalog_entry.get("default_model"),
                api_key=merged_kwargs.get("api_key") or settings.openai_api_key
            )
        elif cat_type == "anthropic":
            from .anthropic_provider import AnthropicProvider
            return AnthropicProvider(
                model=merged_kwargs.get("model") or catalog_entry.get("default_model"),
                api_key=merged_kwargs.get("api_key") or settings.anthropic_api_key
            )
        elif cat_type == "ollama":
            from .ollama import OllamaProvider
            return OllamaProvider(
                model=merged_kwargs.get("model") or catalog_entry.get("default_model"),
                base_url=merged_kwargs.get("base_url") or catalog_entry.get("default_base_url"),
                api_key=merged_kwargs.get("api_key") or settings.ollama_api_key
            )

    # 3. Fallback generic openai-compatible
    from .openai_compatible import OpenAICompatibleProvider
    return OpenAICompatibleProvider(
        model=merged_kwargs.get("model", "llama3"),
        base_url=merged_kwargs.get("base_url", "http://localhost:8080/v1"),
        api_key=merged_kwargs.get("api_key", "no-key"),
        provider_id=name
    )


def list_providers() -> list[dict]:
    """
    Mengembalikan daftar seluruh provider aktif untuk dropdown UI.
    """
    result = []
    user_settings = load_user_ai_settings()

    # Masukkan preset penting dari catalog
    for p_id, item in AI_CATALOG.items():
        user_cfg = user_settings.get(p_id, {})
        has_key = bool(user_cfg.get("api_key") or getattr(settings, item.get("key_env", "").lower(), None))
        
        # Ollama dan provider lokal selalu aktif
        is_local = item.get("category") == "local"
        
        result.append({
            "id": p_id,
            "name": item.get("name", p_id),
            "category": item.get("category", "global"),
            "badge": item.get("badge", ""),
            "icon": item.get("icon", "bi-cpu"),
            "default_model": user_cfg.get("model") or item.get("default_model", ""),
            "default_base_url": user_cfg.get("base_url") or item.get("default_base_url", ""),
            "is_configured": has_key or is_local,
            "popular_models": item.get("popular_models", [])
        })

    return result


# Daftarkan modul dasar
register_provider("ollama", "backend.providers.ollama", "OllamaProvider", {
    "api_key": settings.ollama_api_key,
    "base_url": settings.ollama_base_url,
    "model": settings.ollama_model
})
register_provider("openai", "backend.providers.openai_provider", "OpenAIProvider", {
    "api_key": settings.openai_api_key,
    "model": settings.openai_model
})
register_provider("anthropic", "backend.providers.anthropic_provider", "AnthropicProvider", {
    "api_key": settings.anthropic_api_key,
    "model": settings.anthropic_model
})
register_provider("gemini", "backend.providers.gemini_provider", "GeminiProvider", {
    "api_key": settings.gemini_api_key,
    "model": settings.gemini_model
})
register_provider("openai_compatible", "backend.providers.openai_compatible", "OpenAICompatibleProvider", {
    "api_key": settings.openai_compatible_api_key,
    "base_url": settings.openai_compatible_base_url,
    "model": settings.openai_compatible_model,
})
