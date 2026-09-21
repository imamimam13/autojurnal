"""
Katalog Komprehensif Provider AI untuk AutoJurnal.
Menyediakan preset lengkap endpoint resmi, model bawaan, kategori, dan konfigurasi default.
"""

from typing import Dict, Any, List

AI_CATALOG: Dict[str, Dict[str, Any]] = {
    # --------------------------------------------------------------------------
    # 1. NVIDIA NIM & Global AI Cloud Providers
    # --------------------------------------------------------------------------
    "nvidia": {
        "id": "nvidia",
        "name": "NVIDIA NIM / API Catalog",
        "category": "global",
        "badge": "NVIDIA Cloud",
        "icon": "bi-gpu-card",
        "type": "openai_compatible",
        "default_base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "nvidia/llama-3.1-nemotron-70b-instruct",
        "popular_models": [
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "meta/llama-3.3-70b-instruct",
            "deepseek-ai/deepseek-r1",
            "mistralai/mistral-large-2-instruct",
            "nvidia/nemotron-4-340b-instruct",
            "meta/llama-3.1-8b-instruct"
        ],
        "key_env": "NVIDIA_API_KEY",
        "doc_url": "https://build.nvidia.com"
    },
    "gemini": {
        "id": "gemini",
        "name": "Google Gemini",
        "category": "global",
        "badge": "Google AI",
        "icon": "bi-google",
        "type": "gemini",
        "default_base_url": "",
        "default_model": "gemini-2.0-flash",
        "popular_models": [
            "gemini-2.0-flash",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash"
        ],
        "key_env": "GEMINI_API_KEY",
        "doc_url": "https://aistudio.google.com"
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "category": "global",
        "badge": "Official API",
        "icon": "bi-cpu",
        "type": "openai",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "popular_models": [
            "gpt-4o-mini",
            "gpt-4o",
            "o3-mini",
            "o1",
            "gpt-4-turbo"
        ],
        "key_env": "OPENAI_API_KEY",
        "doc_url": "https://platform.openai.com"
    },
    "anthropic": {
        "id": "anthropic",
        "name": "Anthropic Claude",
        "category": "global",
        "badge": "Claude AI",
        "icon": "bi-chat-square-quote",
        "type": "anthropic",
        "default_base_url": "https://api.anthropic.com",
        "default_model": "claude-3-haiku-20240307",
        "popular_models": [
            "claude-3-7-sonnet-20250219",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-haiku-20240307"
        ],
        "key_env": "ANTHROPIC_API_KEY",
        "doc_url": "https://console.anthropic.com"
    },
    "groq": {
        "id": "groq",
        "name": "Groq LPU",
        "category": "global",
        "badge": "Ultra Fast",
        "icon": "bi-lightning-charge",
        "type": "openai_compatible",
        "default_base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "popular_models": [
            "llama-3.3-70b-versatile",
            "deepseek-r1-distill-llama-70b",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768"
        ],
        "key_env": "GROQ_API_KEY",
        "doc_url": "https://console.groq.com"
    },
    "xai": {
        "id": "xai",
        "name": "xAI (Grok)",
        "category": "global",
        "badge": "xAI",
        "icon": "bi-slash-circle",
        "type": "openai_compatible",
        "default_base_url": "https://api.x.ai/v1",
        "default_model": "grok-2-latest",
        "popular_models": [
            "grok-2-latest",
            "grok-2-vision-latest",
            "grok-beta"
        ],
        "key_env": "XAI_API_KEY",
        "doc_url": "https://console.x.ai"
    },
    "mistral": {
        "id": "mistral",
        "name": "Mistral AI",
        "category": "global",
        "badge": "Mistral",
        "icon": "bi-wind",
        "type": "openai_compatible",
        "default_base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-large-latest",
        "popular_models": [
            "mistral-large-latest",
            "mistral-small-latest",
            "codestral-latest",
            "open-mixtral-8x22b"
        ],
        "key_env": "MISTRAL_API_KEY",
        "doc_url": "https://console.mistral.ai"
    },
    "perplexity": {
        "id": "perplexity",
        "name": "Perplexity AI",
        "category": "global",
        "badge": "Search LLM",
        "icon": "bi-search",
        "type": "openai_compatible",
        "default_base_url": "https://api.perplexity.ai",
        "default_model": "sonar",
        "popular_models": [
            "sonar-pro",
            "sonar",
            "sonar-reasoning"
        ],
        "key_env": "PERPLEXITY_API_KEY",
        "doc_url": "https://www.perplexity.ai"
    },
    "fireworks": {
        "id": "fireworks",
        "name": "Fireworks AI",
        "category": "global",
        "badge": "Speed Cloud",
        "icon": "bi-fire",
        "type": "openai_compatible",
        "default_base_url": "https://api.fireworks.ai/inference/v1",
        "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "popular_models": [
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "accounts/fireworks/models/deepseek-r1",
            "accounts/fireworks/models/qwen2p5-72b-instruct"
        ],
        "key_env": "FIREWORKS_API_KEY",
        "doc_url": "https://fireworks.ai"
    },
    "github_models": {
        "id": "github_models",
        "name": "GitHub Models / Azure AI",
        "category": "global",
        "badge": "GitHub Free/Pro",
        "icon": "bi-github",
        "type": "openai_compatible",
        "default_base_url": "https://models.inference.ai.azure.com",
        "default_model": "gpt-4o",
        "popular_models": [
            "gpt-4o",
            "gpt-4o-mini",
            "Meta-Llama-3.1-70B-Instruct",
            "DeepSeek-R1",
            "Mistral-large-2407"
        ],
        "key_env": "GITHUB_MODELS_API_KEY",
        "doc_url": "https://github.com/marketplace/models"
    },
    "cerebras": {
        "id": "cerebras",
        "name": "Cerebras",
        "category": "global",
        "badge": "Wafer Speed",
        "icon": "bi-speedometer2",
        "type": "openai_compatible",
        "default_base_url": "https://api.cerebras.ai/v1",
        "default_model": "llama3.3-70b",
        "popular_models": [
            "llama3.3-70b",
            "llama3.1-8b"
        ],
        "key_env": "CEREBRAS_API_KEY",
        "doc_url": "https://cloud.cerebras.ai"
    },
    "sambanova": {
        "id": "sambanova",
        "name": "SambaNova",
        "category": "global",
        "badge": "SN Cloud",
        "icon": "bi-diagram-3",
        "type": "openai_compatible",
        "default_base_url": "https://api.sambanova.ai/v1",
        "default_model": "Meta-Llama-3.3-70B-Instruct",
        "popular_models": [
            "Meta-Llama-3.3-70B-Instruct",
            "DeepSeek-R1-Distill-Llama-70B",
            "Qwen2.5-72B-Instruct"
        ],
        "key_env": "SAMBANOVA_API_KEY",
        "doc_url": "https://cloud.sambanova.ai"
    },

    # --------------------------------------------------------------------------
    # 2. China AI Providers & Xiaomi MiMo
    # --------------------------------------------------------------------------
    "xiaomi_mimo": {
        "id": "xiaomi_mimo",
        "name": "Xiaomi MiMo / MiLM",
        "category": "china",
        "badge": "Xiaomi AI",
        "icon": "bi-phone",
        "type": "openai_compatible",
        "default_base_url": "https://api.mimo.xiaomi.com/v1",
        "default_model": "mimo-v1",
        "popular_models": [
            "mimo-v1",
            "mimo-chat",
            "milm-70b"
        ],
        "key_env": "XIAOMI_MIMO_API_KEY",
        "doc_url": "https://mimo.xiaomi.com"
    },
    "deepseek": {
        "id": "deepseek",
        "name": "DeepSeek",
        "category": "china",
        "badge": "Official V3/R1",
        "icon": "bi-star-fill",
        "type": "openai_compatible",
        "default_base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "popular_models": [
            "deepseek-chat",
            "deepseek-reasoner"
        ],
        "key_env": "DEEPSEEK_API_KEY",
        "doc_url": "https://platform.deepseek.com"
    },
    "qwen": {
        "id": "qwen",
        "name": "Alibaba Qwen (DashScope)",
        "category": "china",
        "badge": "Alibaba Cloud",
        "icon": "bi-cloud-check",
        "type": "openai_compatible",
        "default_base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "popular_models": [
            "qwen-plus",
            "qwen-max",
            "qwen-turbo",
            "qwen2.5-72b-instruct",
            "qwen2.5-32b-instruct",
            "qwen-long"
        ],
        "key_env": "QWEN_API_KEY",
        "doc_url": "https://dashscope.aliyun.com"
    },
    "zhipu": {
        "id": "zhipu",
        "name": "Zhipu AI (GLM)",
        "category": "china",
        "badge": "BigModel GLM-4",
        "icon": "bi-patch-check",
        "type": "openai_compatible",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "popular_models": [
            "glm-4-flash",
            "glm-4-plus",
            "glm-4",
            "glm-4-air",
            "glm-4-long"
        ],
        "key_env": "ZHIPU_API_KEY",
        "doc_url": "https://open.bigmodel.cn"
    },
    "moonshot": {
        "id": "moonshot",
        "name": "Moonshot AI (Kimi)",
        "category": "china",
        "badge": "Kimi AI",
        "icon": "bi-moon-stars",
        "type": "openai_compatible",
        "default_base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-32k",
        "popular_models": [
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "moonshot-v1-128k"
        ],
        "key_env": "MOONSHOT_API_KEY",
        "doc_url": "https://platform.moonshot.cn"
    },
    "minimax": {
        "id": "minimax",
        "name": "MiniMax",
        "category": "china",
        "badge": "MiniMax MoE",
        "icon": "bi-boxes",
        "type": "openai_compatible",
        "default_base_url": "https://api.minimax.chat/v1",
        "default_model": "abab6.5s-chat",
        "popular_models": [
            "abab6.5s-chat",
            "abab6.5-chat",
            "abab5.5-chat"
        ],
        "key_env": "MINIMAX_API_KEY",
        "doc_url": "https://api.minimax.chat"
    },
    "doubao": {
        "id": "doubao",
        "name": "ByteDance Doubao (Volcano)",
        "category": "china",
        "badge": "ByteDance Ark",
        "icon": "bi-soundwave",
        "type": "openai_compatible",
        "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": "doubao-pro-32k",
        "popular_models": [
            "doubao-pro-32k",
            "doubao-lite-32k",
            "doubao-pro-128k"
        ],
        "key_env": "DOUBAO_API_KEY",
        "doc_url": "https://www.volcengine.com/product/ark"
    },
    "qianfan": {
        "id": "qianfan",
        "name": "Baidu Qianfan (ERNIE)",
        "category": "china",
        "badge": "Baidu AI",
        "icon": "bi-shield-check",
        "type": "openai_compatible",
        "default_base_url": "https://qianfan.baidubce.com/v2",
        "default_model": "ernie-4.0-turbo-8k",
        "popular_models": [
            "ernie-4.0-turbo-8k",
            "ernie-3.5-8k",
            "ernie-speed-128k"
        ],
        "key_env": "QIANFAN_API_KEY",
        "doc_url": "https://cloud.baidu.com/product/wenxinworkshop"
    },
    "hunyuan": {
        "id": "hunyuan",
        "name": "Tencent Hunyuan",
        "category": "china",
        "badge": "Tencent Cloud",
        "icon": "bi-intersect",
        "type": "openai_compatible",
        "default_base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "default_model": "hunyuan-standard",
        "popular_models": [
            "hunyuan-standard",
            "hunyuan-pro",
            "hunyuan-lite"
        ],
        "key_env": "HUNYUAN_API_KEY",
        "doc_url": "https://cloud.tencent.com/product/hunyuan"
    },
    "yi": {
        "id": "yi",
        "name": "01.AI (Yi / Lingyiwanwu)",
        "category": "china",
        "badge": "01.AI",
        "icon": "bi-lightbulb",
        "type": "openai_compatible",
        "default_base_url": "https://api.lingyiwanwu.com/v1",
        "default_model": "yi-large",
        "popular_models": [
            "yi-large",
            "yi-medium",
            "yi-spark",
            "yi-large-rag"
        ],
        "key_env": "YI_API_KEY",
        "doc_url": "https://platform.lingyiwanwu.com"
    },
    "stepfun": {
        "id": "stepfun",
        "name": "StepFun (Jieyuexingchen)",
        "category": "china",
        "badge": "StepFun",
        "icon": "bi-stairs",
        "type": "openai_compatible",
        "default_base_url": "https://api.stepfun.com/v1",
        "default_model": "step-1-32k",
        "popular_models": [
            "step-1-8k",
            "step-1-32k",
            "step-1-128k",
            "step-2-16k"
        ],
        "key_env": "STEPFUN_API_KEY",
        "doc_url": "https://platform.stepfun.com"
    },
    "baichuan": {
        "id": "baichuan",
        "name": "Baichuan AI",
        "category": "china",
        "badge": "Baichuan",
        "icon": "bi-compass",
        "type": "openai_compatible",
        "default_base_url": "https://api.baichuan-ai.com/v1",
        "default_model": "Baichuan4",
        "popular_models": [
            "Baichuan4",
            "Baichuan3-Turbo",
            "Baichuan2-Turbo"
        ],
        "key_env": "BAICHUAN_API_KEY",
        "doc_url": "https://platform.baichuan-ai.com"
    },

    # --------------------------------------------------------------------------
    # 3. Multi-Model Routers & Aggregators
    # --------------------------------------------------------------------------
    "openrouter": {
        "id": "openrouter",
        "name": "OpenRouter",
        "category": "router",
        "badge": "Global Hub",
        "icon": "bi-hdd-network",
        "type": "openai_compatible",
        "default_base_url": "https://openrouter.ai/api/v1",
        "default_model": "auto",
        "popular_models": [
            "auto",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.0-flash-001",
            "deepseek/deepseek-r1",
            "meta-llama/llama-3.3-70b-instruct"
        ],
        "key_env": "OPENROUTER_API_KEY",
        "doc_url": "https://openrouter.ai"
    },
    "siliconflow": {
        "id": "siliconflow",
        "name": "SiliconFlow (SiliconCloud)",
        "category": "router",
        "badge": "China Cloud Hub",
        "icon": "bi-cpu-fill",
        "type": "openai_compatible",
        "default_base_url": "https://api.siliconflow.cn/v1",
        "default_model": "deepseek-ai/DeepSeek-V3",
        "popular_models": [
            "deepseek-ai/DeepSeek-V3",
            "deepseek-ai/DeepSeek-R1",
            "Qwen/Qwen2.5-72B-Instruct",
            "THUDM/glm-4-9b-chat"
        ],
        "key_env": "SILICONFLOW_API_KEY",
        "doc_url": "https://siliconflow.cn"
    },
    "together": {
        "id": "together",
        "name": "Together AI",
        "category": "router",
        "badge": "OpenSource Cloud",
        "icon": "bi-people",
        "type": "openai_compatible",
        "default_base_url": "https://api.together.xyz/v1",
        "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "popular_models": [
            "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            "deepseek-ai/DeepSeek-R1",
            "Qwen/Qwen2.5-72B-Instruct-Turbo"
        ],
        "key_env": "TOGETHER_API_KEY",
        "doc_url": "https://together.ai"
    },
    "deepinfra": {
        "id": "deepinfra",
        "name": "DeepInfra",
        "category": "router",
        "badge": "Pay-Per-Token",
        "icon": "bi-server",
        "type": "openai_compatible",
        "default_base_url": "https://api.deepinfra.com/v1/openai",
        "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
        "popular_models": [
            "meta-llama/Meta-Llama-3.1-70B-Instruct",
            "deepseek-ai/DeepSeek-R1",
            "Qwen/Qwen2.5-72B-Instruct"
        ],
        "key_env": "DEEPINFRA_API_KEY",
        "doc_url": "https://deepinfra.com"
    },
    "novita": {
        "id": "novita",
        "name": "Novita AI",
        "category": "router",
        "badge": "GPU Cloud",
        "icon": "bi-window-stack",
        "type": "openai_compatible",
        "default_base_url": "https://api.novita.ai/v3/openai",
        "default_model": "deepseek/deepseek-r1",
        "popular_models": [
            "deepseek/deepseek-r1",
            "meta-llama/llama-3.1-70b-instruct"
        ],
        "key_env": "NOVITA_API_KEY",
        "doc_url": "https://novita.ai"
    },
    "custom_router": {
        "id": "custom_router",
        "name": "9Router / OmniRouter / One-API",
        "category": "router",
        "badge": "Self-Hosted Gateway",
        "icon": "bi-signpost-split",
        "type": "openai_compatible",
        "default_base_url": "http://localhost:3000/v1",
        "default_model": "gpt-4o",
        "popular_models": [
            "default",
            "gpt-4o",
            "claude-3-5-sonnet",
            "gemini-2.0-flash",
            "deepseek-chat"
        ],
        "key_env": "CUSTOM_ROUTER_API_KEY",
        "doc_url": ""
    },

    # --------------------------------------------------------------------------
    # 4. Local & Self-Hosted Engine
    # --------------------------------------------------------------------------
    "ollama": {
        "id": "ollama",
        "name": "Ollama (Local / Remote Cloud)",
        "category": "local",
        "badge": "Local & Multi-Host",
        "icon": "bi-laptop",
        "type": "ollama",
        "default_base_url": "http://localhost:11434",
        "default_model": "gemma3:12b",
        "popular_models": [
            "gemma3:12b",
            "llama3.3",
            "qwen2.5:14b",
            "deepseek-r1:14b",
            "gemma4:31b"
        ],
        "key_env": "OLLAMA_API_KEY",
        "doc_url": "https://ollama.com"
    },
    "lmstudio": {
        "id": "lmstudio",
        "name": "LM Studio",
        "category": "local",
        "badge": "Local GUI",
        "icon": "bi-display",
        "type": "openai_compatible",
        "default_base_url": "http://localhost:1234/v1",
        "default_model": "default",
        "popular_models": ["default"],
        "key_env": "LMSTUDIO_API_KEY",
        "doc_url": "https://lmstudio.ai"
    },
    "vllm": {
        "id": "vllm",
        "name": "vLLM / TGI",
        "category": "local",
        "badge": "High Throughput",
        "icon": "bi-rocket-takeoff",
        "type": "openai_compatible",
        "default_base_url": "http://localhost:8000/v1",
        "default_model": "default",
        "popular_models": ["default"],
        "key_env": "VLLM_API_KEY",
        "doc_url": "https://docs.vllm.ai"
    },
    "llamacpp": {
        "id": "llamacpp",
        "name": "llama.cpp / KoboldCPP",
        "category": "local",
        "badge": "C++ Inference",
        "icon": "bi-file-earmark-binary",
        "type": "openai_compatible",
        "default_base_url": "http://localhost:8080/v1",
        "default_model": "default",
        "popular_models": ["default"],
        "key_env": "LLAMACPP_API_KEY",
        "doc_url": "https://github.com/ggerganov/llama.cpp"
    },
    "openai_compatible": {
        "id": "openai_compatible",
        "name": "Custom OpenAI Compatible",
        "category": "custom",
        "badge": "Any Endpoint",
        "icon": "bi-sliders",
        "type": "openai_compatible",
        "default_base_url": "http://localhost:8080/v1",
        "default_model": "llama3",
        "popular_models": ["llama3", "default"],
        "key_env": "OPENAI_COMPATIBLE_API_KEY",
        "doc_url": ""
    }
}


def get_catalog_list() -> List[Dict[str, Any]]:
    """Mengembalikan list provider dalam format terurut rapi untuk antarmuka UI."""
    return list(AI_CATALOG.values())


def get_catalog_entry(provider_id: str) -> Dict[str, Any]:
    """Mengambil preset spesifik provider berdasarkan ID-nya."""
    return AI_CATALOG.get(provider_id, {
        "id": provider_id,
        "name": provider_id,
        "category": "custom",
        "badge": "Custom",
        "icon": "bi-cpu",
        "type": "openai_compatible",
        "default_base_url": "",
        "default_model": "default",
        "popular_models": [],
        "key_env": "",
        "doc_url": ""
    })
