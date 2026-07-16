# AutoJurnal

AI-powered academic journal and textbook generator with multi-agent orchestration, RAG-based source grounding, web research, diagram generation, and chunked processing.

## Features

- **Multi-Agent Architecture** — 10 agents per section: Methodology Analyst → Lead Researcher → Source Reviewer → Lead Writer → **Lead Storyteller** → Peer Reviewer → Researcher Revision → Writer Revision → Storyteller Revision → Humanizer
- **Web Research** — Bing Web + Bing News + Google Scholar via httpx (no browser binary needed)
- **RAG (Retrieval-Augmented Generation)** — PDF scraping, chunking, and semantic search via Qdrant in-memory + TF-IDF (or FastEmbed)
- **Diagrams** — Matplotlib (bar/line/pie/venn/gantt) + Mermaid (flowchart/concept_map, rendered via CDN — no `dot` binary required)
- **Multi-Provider** — Ollama, Google Gemini, OpenAI, Anthropic, OpenAI Compatible (e.g. llama.cpp, LM Studio, vLLM)
- **Templates** — 10 preset templates (IMRAD, Systematic Review, Case Report, Lab Reports, etc.) with category grouping + user-uploaded templates
- **Restructure** — Heading detection, Google Docs/Drive download, chunked LLM restructure
- **Human Review** — `.docx` comment extraction, Google Docs link parsing, chunked revision
- **Translate** — Chunked translation preserving markdown, citations, and diagram blocks
- **Textbook Mode** — Curriculum designer + per-chapter generation with RAG
- **Programmatic References** — Real OpenAlex paper data, never from LLM
- **Multi-Language** — Indonesian and English

## Architecture

```
User → Frontend (vanilla HTML + Bootstrap + JS)
              │
              └── FastAPI Backend
                      │
                      ├── Search (OpenAlex API)
                      ├── Research (Bing Web, News, Google Scholar)
                      ├── RAG (PyMuPDF → Chunker → Qdrant/TF-IDF)
                      │
                      ├── Generate
                      │   ├── Standard mode (single prompt)
                      │   ├── Multi-Agent mode (10 agents × section)
                      │   └── Textbook mode (curriculum + chapters)
                      │
                      ├── Restructure (heading detection + LLM)
                      ├── Review (chunked revision + docx parse)
                      └── Translate (chunked, structure-preserving)
```

### Multi-Agent Pipeline (Journal)

Each section (Judul/Abstrak, Pendahuluan, Tinjauan Pustaka, Metode, Temuan, Penutup) passes through:

```
0. Methodology Analyst    → Determine paradigm + analysis method (runs once)
1. Lead Researcher        → Research plan
2. Source Reviewer         → Synthesized findings from RAG
3. Lead Writer             → First draft
4. Lead Storyteller        → Narrative/descriptive enrichment
5. Peer Reviewer           → Critique (6 aspects)
6. Lead Researcher         → Revised plan
7. Lead Writer             → Revised draft
8. Lead Storyteller        → Enrich revision
9. Humanizer               → Natural language polish
```

### Textbook Pipeline

```
0. Methodology Analyst     → Determine methodology (runs once)
1. Curriculum Designer     → Generate chapter list
   (per chapter:)
2. Lead Researcher         → Chapter plan
3. Source Reviewer          → Extract concepts
4. Lead Writer              → Write chapter
5. Lead Storyteller         → Enrich with illustrations/analogies
6. Humanizer                → Natural language polish
```

## Prerequisites

- **Python 3.11+** (3.14 recommended)
- **Ollama** (recommended) or API keys for cloud providers
- **Docker** (optional, for running Qdrant server — not needed for in-memory mode)

## Installation

```bash
git clone https://github.com/imamimam13/autojurnal.git
cd autojurnal

python3 -m venv venv
source venv/bin/activate

# Install dependencies (matplotlib needs font cache set)
MPLCONFIGDIR=/tmp/matplotlib pip install -r backend/requirements.txt

# Install optional provider dependencies (OpenAI, Anthropic, Gemini, OpenAI Compatible)
pip install -r backend/requirements-optional.txt

# Install matplotlib separately if needed
MPLCONFIGDIR=/tmp/matplotlib pip install matplotlib matplotlib-venn
```

> **Note:** `fastembed` requires `onnxruntime`. If installation fails, the app falls back to TF-IDF automatically. Qdrant in-memory mode uses `qdrant-client<1.13` for Python 3.14 compatibility.

## Configuration

Copy `.env.example` to `.env` and fill in credentials:

```env
# OpenAlex (optional, for higher rate limits)
OPENALEX_API_KEY=your_key_here

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:12b

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-haiku-20240307

# Google Gemini
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.0-flash

# OpenAI Compatible (e.g. llama.cpp, LM Studio, vLLM)
OPENAI_COMPATIBLE_API_KEY=
OPENAI_COMPATIBLE_MODEL=llama3
OPENAI_COMPATIBLE_BASE_URL=http://localhost:8080/v1
```

## Usage

```bash
# Start Ollama (Docker)
docker start ollama  # or: docker run -d --name ollama -p 11434:11434 ollama/ollama

# Pull a model
docker exec ollama ollama pull gemma3:12b

# Start the server (Development mode with auto-reload)
cd /Users/imamimam/Documents/GitHub/autojurnal
MPLCONFIGDIR=/tmp/matplotlib venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Start the server in the background (nohup mode for persistence)
MPLCONFIGDIR=/tmp/matplotlib nohup venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &

# View background logs
tail -f server.log

# Stop the background server
pkill -f "uvicorn backend.main:app"
```

Open `http://localhost:8000` in your browser.

1. **Search** — Enter theme, adjust year range, click Search
2. **Select** — Choose papers from OpenAlex results
3. **(Optional) Research** — Check "🔍 Research" to fetch live web sources
4. **Generate** — Select provider, template, toggle Multi-Agent, click Generate

### Modes

| Mode | Description | LLM Calls |
|------|-------------|-----------|
| **Standard** | Single prompt, 2-3 parts | ~3 |
| **Multi-Agent** | 10 agent steps × 6 sections | ~55 + 1 methodology |
| **Textbook** | Curriculum + 10 chapters | ~60 + 1 methodology |

### Other Features

- **Restructure** — Paste document text or Google Docs link, select template → AI restructures content with proper headings
- **Review** — Upload `.docx` with Word comments or paste Google Docs link → chunked revision based on feedback
- **Translate** — Paste text, select source/target language → chunked translation preserving structure
- **Templates** — Browse preset templates by category, upload guideline PDFs to create custom templates
- **Diagrams** — Toggle "📊 Has Data" to enable data-driven charts; flowchart/concept_map work without data

## Project Structure

```
autojurnal/
├── backend/
│   ├── main.py                    # FastAPI app & all endpoints
│   ├── config.py                  # Pydantic settings from .env
│   │
│   ├── generator/
│   │   ├── agents.py              # Multi-agent pipeline (10 agents)
│   │   ├── journal.py             # Standard journal generation
│   │   └── textbook.py            # Textbook generation
│   │
│   ├── providers/
│   │   ├── base.py                # LLMProvider abstract interface
│   │   ├── factory.py             # Provider registry + discovery
│   │   ├── ollama.py              # Ollama provider (num_predict=8192, retry)
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   └── gemini_provider.py
│   │
│   ├── research/
│   │   ├── searcher.py            # Bing Web + News + Google Scholar (httpx, Safari UA)
│   │   ├── scraper.py             # Text extraction (httpx fallback)
│   │   ├── pipeline.py            # Background research jobs
│   │   ├── models.py              # ScrapedSource, ResearchJob
│   │   └── router.py              # /api/research endpoints
│   │
│   ├── rag/
│   │   ├── scraper.py             # Async PDF scraping (PyMuPDF)
│   │   ├── chunker.py             # Text chunking (1000/200, safe infinite loop)
│   │   └── store.py               # Qdrant in-memory + TF-IDF fallback
│   │
│   ├── diagrams/
│   │   ├── engine.py              # 7 render types: bar, line, pie, venn, gantt, flowchart, concept_map
│   │   └── prompts.py             # Diagram instruction builder (has_data-aware)
│   │
│   ├── restructure/
│   │   ├── parser.py              # Heading detection from text
│   │   ├── gdrive.py              # Google Docs download (HTML → markdown headings)
│   │   └── restructure.py         # Chunked LLM restructure
│   │
│   ├── templates/
│   │   ├── loader.py              # Template load/save/list/delete/parse
│   │   └── *.json                 # 10 preset templates (medical, physics, chemistry, math, etc.)
│   │
│   ├── search/
│   │   └── openalex.py            # OpenAlex paper search API
│   │
│   └── requirements.txt           # Python dependencies
│
├── frontend/
│   ├── index.html                 # Single-page app (Bootstrap 5.3.3)
│   ├── app.js                     # All UI logic + API calls
│   └── style.css                  # Custom styles
│
├── .env.example
└── README.md
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `QdrantClient(":memory:")` hangs | Pin `qdrant-client<1.13` (incompatible with Python 3.14) |
| `grpc.aio` import hangs | Downgrade qdrant-client to <1.13 (avoids grpc.aio issue) |
| Ollama 504 / timeout | Chunked processing (3000 chars) + `num_predict=8192` + 3× retry |
| Bing captcha | Uses Safari UA only (no Accept/Accept-Language headers) |
| Matplotlib font cache | Set `MPLCONFIGDIR=/tmp/matplotlib` before running |
| CloakBrowser binary | Not needed — research uses httpx-only by default |
| Flowchart not rendering | No `dot` binary needed — uses frontend mermaid.js CDN |

## License

MIT
