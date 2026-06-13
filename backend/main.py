from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import settings
from .search.openalex import OpenAlexSearcher, Paper
from .generator.journal import build_system_prompt, build_part_prompt, count_parts
from .generator.agents import generate_multi_agent
from .providers import get_provider, list_providers
from .rag.scraper import scrape_all
from .rag.store import store

app = FastAPI(title=settings.app_name, version="1.0.0")


def format_reference(p: Paper) -> str:
    if len(p.authors) == 0:
        author_str = "Unknown"
    elif len(p.authors) == 1:
        author_str = p.authors[0]
    elif len(p.authors) == 2:
        author_str = f"{p.authors[0]} & {p.authors[1]}"
    else:
        author_str = f"{p.authors[0]} et al."

    year = p.year or "n.d."

    if p.doi:
        url = f"https://doi.org/{p.doi}"
    elif p.url:
        url = p.url
    elif p.openalex_url:
        url = p.openalex_url
    else:
        url = ""

    title = (p.title or "Untitled").rstrip(".")
    parts = [f"{author_str} ({year}). {title}."]
    if p.source:
        parts.append(f" {p.source}.")
    if url:
        parts.append(f" URL: {url}")

    return "".join(parts)


def replace_references(journal: str, papers: list[Paper], language: str) -> str:
    id_heading = "## Daftar Pustaka"
    en_heading = "## References"
    heading = id_heading if language == "id" else en_heading
    idx = journal.find(heading)
    if idx == -1:
        alt = en_heading if language == "id" else id_heading
        idx = journal.find(alt)
        if idx != -1:
            heading = alt

    def sort_key(p: Paper) -> str:
        first = p.authors[0] if p.authors else "Unknown"
        last = first.rsplit(" ", 1)[-1]
        return last.lower()

    sorted_papers = sorted(papers, key=sort_key)
    refs = "\n\n".join(format_reference(p) for p in sorted_papers)

    if idx == -1:
        return journal + f"\n\n{heading}\n\n{refs}"

    before = journal[:idx].rstrip("\n")
    return f"{before}\n\n{heading}\n\n{refs}"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    theme: str
    from_year: Optional[int] = None
    to_year: Optional[int] = None
    year_range: Optional[int] = None
    max_papers: int = Field(default=15, ge=5, le=200)
    language: str = Field(default="en", pattern="^(en|id)$")
    openalex_api_key: Optional[str] = None


class SearchResponse(BaseModel):
    papers: list[dict]
    total_found: int


class GenerateRequest(BaseModel):
    theme: str
    papers: list[dict]
    language: str = Field(default="en", pattern="^(en|id)$")
    provider: str = Field(default="ollama")
    provider_model: Optional[str] = None
    api_key: Optional[str] = None
    provider_base_url: Optional[str] = None
    target_length: str = Field(default="medium", pattern="^(short|medium|long|extended)$")
    multi_agent: bool = False


class GenerateResponse(BaseModel):
    journal: str
    provider_used: str
    token_usage: Optional[dict] = None


class ProviderInfo(BaseModel):
    id: str
    name: str


class SaveSettingsRequest(BaseModel):
    provider: str
    api_key: str


PROVIDER_ENV_MAP = {
    "ollama": "OLLAMA_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


@app.put("/api/settings")
async def save_settings(req: SaveSettingsRequest):
    env_var = PROVIDER_ENV_MAP.get(req.provider)
    if not env_var:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        raise HTTPException(status_code=500, detail=".env file not found")

    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(env_var):
            lines[i] = f"{env_var}={req.api_key}\n"
            found = True
            break

    if not found:
        lines.append(f"\n{env_var}={req.api_key}\n")

    env_path.write_text("".join(lines), encoding="utf-8")
    print(f"[Settings] Saved {env_var} to .env")
    return {"status": "ok"}


@app.get("/api/providers", response_model=list[ProviderInfo])
async def get_providers():
    return list_providers()


@app.post("/api/search", response_model=SearchResponse)
async def search_papers(req: SearchRequest):
    searcher = OpenAlexSearcher(max_results=req.max_papers, api_key=req.openalex_api_key)

    from_year = req.from_year
    to_year = req.to_year

    if not from_year and not to_year and req.year_range:
        current_year = datetime.now().year
        from_year = current_year - req.year_range

    papers = await searcher.search(
        query=req.theme,
        from_year=from_year,
        to_year=to_year,
    )

    return SearchResponse(
        papers=[
            {
                "title": p.title,
                "abstract": p.abstract,
                "authors": p.authors,
                "year": p.year,
                "doi": p.doi,
                "openalex_url": p.openalex_url,
                "url": p.url,
                "pdf_url": p.pdf_url,
                "source": p.source,
                "cited_by_count": p.cited_by_count,
                "relevance_score": p.relevance_score,
                "concepts": p.concepts,
            }
            for p in papers
        ],
        total_found=len(papers),
    )


@app.post("/api/generate", response_model=GenerateResponse)
async def generate_journal(req: GenerateRequest):
    provider_kwargs = {}
    if req.provider_model:
        provider_kwargs["model"] = req.provider_model
    if req.api_key:
        provider_kwargs["api_key"] = req.api_key
    if req.provider_base_url:
        provider_kwargs["base_url"] = req.provider_base_url

    provider = get_provider(req.provider, **provider_kwargs)
    if not provider:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{req.provider}' not available. Choose from: {[p['id'] for p in list_providers()]}",
        )

    system_prompt = build_system_prompt(req.language)

    papers = [
        Paper(
            title=p.get("title", "Untitled"),
            abstract=p.get("abstract"),
            authors=p.get("authors", []),
            year=p.get("year"),
            doi=p.get("doi"),
            openalex_url=p.get("openalex_url"),
            url=p.get("url"),
            pdf_url=p.get("pdf_url"),
            source=p.get("source"),
            cited_by_count=p.get("cited_by_count", 0),
            relevance_score=p.get("relevance_score"),
            concepts=p.get("concepts", []),
        )
        for p in req.papers
    ]

    # RAG: scrape PDFs and index chunks
    MAX_SCRAPE = 8
    sorted_papers = sorted(papers, key=lambda p: p.relevance_score or 0, reverse=True)
    scrape_targets = sorted_papers[:MAX_SCRAPE]
    abstract_targets = sorted_papers[MAX_SCRAPE:]
    print(f"[RAG] Scraping top {len(scrape_targets)} PDFs + {len(abstract_targets)} abstracts")
    try:
        chunks = await scrape_all(scrape_targets, max_concurrent=5)
        scraped_indices = set()
        for local_idx, chunk_list in chunks.items():
            p = scrape_targets[local_idx]
            original_idx = papers.index(p)
            scraped_indices.add(original_idx)
            store.add_chunks(original_idx, chunk_list, {
                "title": p.title,
                "authors": p.authors,
                "year": p.year,
                "source": p.source,
            })
        # Fallback: papers whose PDF failed to scrape → use abstract
        for p in scrape_targets:
            original_idx = papers.index(p)
            if original_idx not in scraped_indices and p.abstract:
                store.add_chunks(original_idx, [p.abstract], {
                    "title": p.title,
                    "authors": p.authors,
                    "year": p.year,
                    "source": p.source,
                })
        # Lower-relevance papers: use abstract
        for p in abstract_targets:
            if p.abstract:
                original_idx = papers.index(p)
                store.add_chunks(original_idx, [p.abstract], {
                    "title": p.title,
                    "authors": p.authors,
                    "year": p.year,
                    "source": p.source,
                })
        print(f"[RAG] Indexed {len(store)} chunks ({len(chunks)} PDFs + abstracts)")
        # Debug: peek at first chunk to verify text exists
        if store.chunks:
            first = store.chunks[0]["text"][:100]
            print(f"[RAG] First chunk preview: {first!r}")
    except Exception as e:
        print(f"[RAG] Scrape error (continuing without): {e}")

    if req.multi_agent:
        print("[Agent] Using multi-agent generation")
        journal, token_usage = await generate_multi_agent(
            provider=provider,
            papers=papers,
            theme=req.theme,
            language=req.language,
            target_length=req.target_length,
        )
        token_usage["estimated"] = True
    else:
        num_parts = count_parts(req.target_length)
        journal_parts = []
        previous_content = None

        for part in range(1, num_parts + 1):
            section_queries = {
                1: f"{req.theme} introduction background literature review",
                2: f"{req.theme} method findings results discussion",
                3: f"{req.theme} conclusion implications",
            }
            query = section_queries.get(part, req.theme)
            rag_results = store.search(query, top_k=5, min_score=0.05)
            rag_context = store.format_context(rag_results, papers) if rag_results else None
            print(f"[RAG] Part {part}: {len(rag_results)} chunks retrieved")

            prompt = build_part_prompt(
                papers, req.language, req.theme, req.target_length,
                part=part, num_parts=num_parts, previous_content=previous_content,
                rag_context=rag_context,
            )
            part_text = await provider.generate(prompt, system_prompt=system_prompt)

            if part != num_parts:
                for marker in ["\n## References", "\nReferences", "\n## Daftar Pustaka", "\nDaftar Pustaka"]:
                    idx = part_text.find(marker)
                    if idx != -1:
                        part_text = part_text[:idx]

            if part > 1:
                if part == 2:
                    new_sections = ["## Metode Penelitian", "## Temuan dan Pembahasan", "## Research Method", "## Findings and Discussion"]
                else:
                    new_sections = ["## Penutup", "## Conclusion"]
                first_new = None
                for s in new_sections:
                    idx = part_text.find(s)
                    if idx != -1:
                        first_new = idx
                        break
                if first_new is not None and first_new > 0:
                    part_text = part_text[first_new:]

            journal_parts.append(part_text)
            previous_content = (previous_content or "") + "\n\n" + part_text

        journal = "\n\n".join(journal_parts)
        token_usage = None

    # Replace LLM-generated references with accurate backend-generated ones
    journal = replace_references(journal, papers, req.language)

    # Clear RAG store to free memory
    store.clear()
    print("[RAG] Store cleared")

    return GenerateResponse(journal=journal, provider_used=provider.display_name, token_usage=token_usage)


frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
