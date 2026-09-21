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

## Quick Start & Installation

### 🍎 macOS / Linux (1-Click Installer)

1. **Jalankan Installer:**
   ```bash
   ./install.sh
   ```
   *Script ini otomatis menyiapkan environment, menginstal dependensi, dan meng-compile `AutoJurnal.app`.*

2. **Jalankan Aplikasi:**
   - **Double-click** file **`AutoJurnal.app`** di folder project (atau pindahkan ke `/Applications` / Desktop).
   - *Aplikasi langsung terbuka dalam Dedicated App Window (tanpa address bar browser).*
   - **Atau via terminal:** `./run.sh`

3. **Hentikan Aplikasi:**
   - Klik ganda `AutoJurnal.app` lalu pilih **Hentikan Server**, atau jalankan `./stop.sh`.

---

### 🪟 Windows (1-Click Installer)

1. **Jalankan Installer:**
   - Double-click **`install.bat`**
   - *Script akan otomatis mengecek Python, membuat virtual environment, menginstal dependensi, dan membuat shortcut **AutoJurnal** di Desktop Windows Anda.*

2. **Jalankan Aplikasi:**
   - **Double-click shortcut `AutoJurnal` di Desktop Anda** (atau double-click `run.bat`).
   - *Aplikasi langsung terbuka dalam Native App Window (Microsoft Edge / Google Chrome App Mode).*

3. **Hentikan Aplikasi:**
   - Double-click **`stop.bat`**

---

## Manual Installation via Terminal (Optional)

```bash
git clone https://github.com/imamimam13/autojurnal.git
cd autojurnal

# macOS / Linux:
python3 -m venv venv
source venv/bin/activate
MPLCONFIGDIR=/tmp/matplotlib pip install -r backend/requirements.txt
./run.sh

# Windows:
python -m venv venv
venv\Scripts\activate
pip install -r backend\requirements.txt
run.bat
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
