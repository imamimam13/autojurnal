# AutoJurnal

AI-powered qualitative research journal generator with multi-agent orchestration, RAG-based source grounding, and programmatic reference management.

## Features

- **Multi-Agent Architecture** — 7 agents per section collaborate in a pipeline: Lead Researcher → Source Reviewer → Lead Writer → Peer Reviewer → Researcher Revision → Writer Revision → Humanizer
- **RAG (Retrieval-Augmented Generation)** — PDF scraping, chunking, and semantic search using TF-IDF or FastEmbed
- **Multi-Provider** — Supports Ollama, Google Gemini, OpenAI, and Anthropic
- **Programmatic Daftar Pustaka** — References generated from real OpenAlex data, never from the LLM
- **Multi-Language** — Supports Indonesian (akademik) and English
- **Auto API Key Save** — Keys entered in the frontend persist to `.env`

## Architecture

```
User → Frontend → FastAPI Backend
                    │
                    ├── Search (OpenAlex API)
                    ├── RAG (PyMuPDF → Chunker → Qdrant)
                    │
                    └── Generate
                        ├── Standard mode (2-3 parts, single prompt)
                        └── Multi-Agent mode (7 agents × 6 sections)
```

### Multi-Agent Pipeline

Each section (Judul/Abstrak, Pendahuluan, Tinjauan Pustaka, Metode, Temuan, Penutup) passes through:

```
1. Lead Researcher      → Research plan
2. Source Reviewer      → Synthesized findings from RAG
3. Lead Writer          → First draft
4. Peer Reviewer        → Critique (6 aspects)
5. Lead Researcher      → Revised plan
6. Lead Writer          → Revised section
7. Humanizer            → Natural language polish
```

### Embedding Backend

Auto-detects the best available option:

| Platform | Embedding | Requirement |
|----------|-----------|-------------|
| Linux x86_64 | FastEmbed (ONNX) | `pip install fastembed` |
| macOS 14+ arm64 | FastEmbed (ONNX) | `pip install fastembed` |
| Windows | FastEmbed (ONNX) | `pip install fastembed` |
| Intel Mac / macOS <14 | TF-IDF (numpy) | Works out of the box |

## Prerequisites

- **Python 3.11+** (3.14 recommended)
- A running Ollama server (for Ollama provider) or API keys for cloud providers

## Installation

```bash
# Clone
git clone https://github.com/yourusername/autojurnal.git
cd autojurnal

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

> **Note:** `fastembed` requires `onnxruntime`, which may not have a wheel for your platform.
> If installation fails, the app falls back to TF-IDF automatically — no manual intervention needed.

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```env
# OpenAlex (optional, for higher rate limits)
OPENALEX_API_KEY=your_key_here

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-haiku-20240307

# Google Gemini
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.0-flash
```

API keys can also be entered in the frontend — they are automatically saved to `.env` when the provider is changed.

## Usage

```bash
# Start the server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.

1. **Search** — Enter a research theme, adjust year range, click Search
2. **Select** — Choose papers from the results
3. **Generate** — Select provider, toggle Multi-Agent, click Generate

### Standard Mode

Generates the journal in 2-3 parts (depending on target length). Each part uses a single LLM call.

### Multi-Agent Mode

Each of the 6 journal sections goes through 7 agent steps (42 LLM calls total).
Produces higher quality output with peer review and humanization.

## Project Structure

```
autojurnal/
├── backend/
│   ├── main.py                 # FastAPI app & endpoints
│   ├── config.py               # Pydantic settings
│   ├── search/
│   │   └── openalex.py         # OpenAlex paper search
│   ├── generator/
│   │   ├── journal.py          # Standard generation logic
│   │   └── agents.py           # Multi-agent pipeline
│   ├── providers/
│   │   ├── base.py             # LLMProvider interface
│   │   ├── factory.py          # Provider registry
│   │   ├── ollama.py
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   └── gemini_provider.py
│   └── rag/
│       ├── scraper.py          # PyMuPDF async PDF scraping
│       ├── chunker.py          # Text chunking (1500/50)
│       └── store.py            # Qdrant in-memory + TF-IDF / FastEmbed
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── requirements.txt
└── README.md
```

## License

MIT
