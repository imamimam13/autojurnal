import hashlib
import sys
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, AsyncGenerator
import os
import re
import tempfile
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))
from config import settings
from search.openalex import OpenAlexSearcher, Paper
from generator.journal import build_system_prompt, build_part_prompt, count_parts
from generator.agents import generate_multi_agent
from generator.textbook import generate_textbook
from providers import get_provider, list_providers
from rag.scraper import scrape_all
from rag.store import store
from templates import load_template, list_templates, save_template, delete_template, parse_upload
from restructure.parser import split_sections
from docx import Document as DocxDocument
from restructure import parse_document, restructure_document as restructure_doc, resolve_link, render_diagrams
from store import store as works_store
from store.works import WorkRecord, format_previous_works_context
from diagrams import extract_and_render_diagrams
from research import research_router

app = FastAPI(title=settings.app_name, version="1.0.0")
app.include_router(research_router)


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


_REF_INLINE_RE = re.compile(
    r"(?:\b[A-Z][a-zA-Z\s&]+(?:\.|,)\s*(?:\d+[\(\),]\s*)+\d+(?:[:\-–]\d+)?\s*(?:\.\s*)?"
    r"(?:DOI\s*:\s*10\.\d{4,}(?:\.\d+)*/[^\s,;]+|https?://[^\s,;]+)?\s*[,;]?\s*)"
    r"|\b(?:DOI\s*:\s*10\.\d{4,}(?:\.\d+)*/[^\s,;]+)"
    r"|\bhttps?://(?:doi\.org|dx\.doi\.org|scholar\.google)[^\s,;)]+",
    re.IGNORECASE,
)


def _strip_inline_references(text: str) -> str:
    """Remove inline journal citations (journal name, volume, pages, DOI, URLs)
    from the body of the document, preserving the References section."""
    ref_headings = re.compile(r"^(##\s*(?:Daftar\s+Pustaka|References))\s*$", re.IGNORECASE | re.MULTILINE)
    match = ref_headings.search(text)
    if match:
        body = text[:match.start()]
        refs = text[match.start():]
    else:
        body = text
        refs = ""

    body = _REF_INLINE_RE.sub("", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    return (body + "\n\n" + refs) if refs else body


async def _setup_rag(papers: list[Paper], paper_hash: str):
    if store.paper_hash == paper_hash:
        print(f"[RAG] Store already has data for this paper set ({len(store)} chunks) — skipping scrape")
        return

    if store.restore_if_exists(paper_hash):
        print(f"[RAG] Restored from disk — skipping scrape")
        return

    store.clear()
    MAX_SCRAPE = 20
    sorted_papers = sorted(papers, key=lambda p: p.relevance_score or 0, reverse=True)
    scrape_targets = sorted_papers[:MAX_SCRAPE]
    abstract_targets = sorted_papers[MAX_SCRAPE:]
    print(f"[RAG] Scraping top {len(scrape_targets)} PDFs + {len(abstract_targets)} abstracts")
    try:
        chunks = await scrape_all(scrape_targets, max_concurrent=10)
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
        for p in scrape_targets:
            original_idx = papers.index(p)
            if original_idx not in scraped_indices and p.abstract:
                store.add_chunks(original_idx, [p.abstract], {
                    "title": p.title,
                    "authors": p.authors,
                    "year": p.year,
                    "source": p.source,
                })
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
        store.set_paper_hash(paper_hash)
    except Exception as e:
        print(f"[RAG] Scrape error (continuing without): {e}")


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
    mode: str = Field(default="journal", pattern="^(journal|textbook)$")
    num_chapters: int = Field(default=10, ge=5, le=50)
    template_id: Optional[str] = None
    has_data: bool = Field(default=False, description="Whether user has real tabulated/research data to visualize")
    user_data: Optional[str] = Field(default=None, description="User-provided research data (CSV/JSON/table)")
    do_research: bool = False
    research_job_id: Optional[str] = None
    library: bool = Field(default=False, description="Check previous works on similar themes to avoid duplication")


class RestructureParseRequest(BaseModel):
    file_url: Optional[str] = None


class RestructureParseResponse(BaseModel):
    source_text: str
    headings: list[dict]
    sections: list[dict]
    has_markdown_headings: bool


class RestructureRequest(BaseModel):
    source_text: str
    template_id: str
    language: str = Field(default="id", pattern="^(en|id)$")
    theme: str = ""
    provider: str = Field(default="ollama")
    provider_model: Optional[str] = None
    api_key: Optional[str] = None
    provider_base_url: Optional[str] = None
    has_data: bool = False
    user_data: Optional[str] = None


class RestructureResponse(BaseModel):
    restructured_text: str
    provider_used: str
    token_usage: Optional[dict] = None


class ReviseRequest(BaseModel):
    source_text: str
    review_text: str
    language: str = Field(default="id", pattern="^(en|id)$")
    provider: str = Field(default="ollama")
    provider_model: Optional[str] = None
    api_key: Optional[str] = None
    provider_base_url: Optional[str] = None


class ReviseResponse(BaseModel):
    revised_text: str
    provider_used: str
    token_usage: Optional[dict] = None


class ReviseParseResponse(BaseModel):
    source_text: str
    review_text: str
    comment_count: int = 0


class TranslateRequest(BaseModel):
    source_text: str
    source_language: str = Field(default="en", pattern="^(en|id)$")
    target_language: str = Field(default="id", pattern="^(en|id)$")
    provider: str = Field(default="ollama")
    provider_model: Optional[str] = None
    api_key: Optional[str] = None
    provider_base_url: Optional[str] = None


class TranslateResponse(BaseModel):
    translated_text: str
    provider_used: str
    token_usage: Optional[dict] = None


class GenerateResponse(BaseModel):
    journal: str
    provider_used: str
    token_usage: Optional[dict] = None


class WorksListResponse(BaseModel):
    works: list[dict]
    total: int


class WorksDeleteResponse(BaseModel):
    status: str


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

    # Research: inject scraped sources from CloakBrowser
    if req.research_job_id:
        from .research import get_job as get_research_job
        research_job = get_research_job(req.research_job_id)
        if research_job and research_job.sources:
            print(f"[Generate] Injecting {len(research_job.sources)} research sources")
            for src in research_job.sources:
                if not src.text:
                    continue
                papers.append(Paper(
                    title=src.title,
                    abstract=src.text[:1000],
                    authors=[],
                    year=None,
                    doi=None,
                    openalex_url=None,
                    url=src.url,
                    pdf_url=None,
                    source=f"research_{src.source}",
                    cited_by_count=0,
                ))

    # RAG: scrape PDFs and index chunks (persistent — data survives restarts)
    paper_ids = "-".join(sorted(p.doi or p.openalex_url or p.title for p in papers))
    paper_hash = hashlib.md5(paper_ids.encode()).hexdigest()
    await _setup_rag(papers, paper_hash)

    template = None
    if req.template_id:
        template = load_template(req.template_id)

    # Librarian: search previous works for context
    prev_works_ctx = ""
    if req.library:
        similar = works_store.search_similar(req.theme, top_k=3, min_score=0.05)
        if similar:
            prev_works_ctx = format_previous_works_context(similar)
            print(f"[Librarian] Found {len(similar)} similar past works")
            if req.multi_agent == False and req.mode != "textbook":
                system_prompt = prev_works_ctx + "\n\n" + system_prompt

    try:
        if req.mode == "textbook":
            print(f"[Textbook] Generating {req.num_chapters} chapters")
            journal, token_usage = await generate_textbook(
                provider=provider, papers=papers, theme=req.theme,
                language=req.language, num_chapters=req.num_chapters,
                template=template, has_data=req.has_data, user_data=req.user_data,
                previous_works_ctx=prev_works_ctx,
            )
            token_usage["estimated"] = True
        elif req.multi_agent:
            print("[Agent] Using multi-agent generation")
            journal, token_usage = await generate_multi_agent(
                provider=provider, papers=papers, theme=req.theme,
                language=req.language, target_length=req.target_length,
                template=template, has_data=req.has_data, user_data=req.user_data,
                previous_works_ctx=prev_works_ctx,
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
                    rag_context=rag_context, has_data=req.has_data, user_data=req.user_data,
                )
                part_text = await provider.generate(prompt, system_prompt=system_prompt)

                if part != num_parts:
                    for marker in ["\n## References", "\nReferences", "\n## Daftar Pustaka", "\nDaftar Pustaka"]:
                        idx = part_text.find(marker)
                        if idx != -1:
                            part_text = part_text[:idx]
                if part > 1:
                    new_sections = (
                        ["## Metode Penelitian", "## Temuan dan Pembahasan", "## Research Method", "## Findings and Discussion"]
                        if part == 2 else ["## Penutup", "## Conclusion"]
                    )
                    for s in new_sections:
                        idx = part_text.find(s)
                        if idx != -1:
                            part_text = part_text[idx:]
                            break
                journal_parts.append(part_text)
                previous_content = (previous_content or "") + "\n\n" + part_text
            journal = "\n\n".join(journal_parts)
            token_usage = None

        journal = extract_and_render_diagrams(journal)
        journal = await render_diagrams(journal)
        journal = replace_references(journal, papers, req.language)
        journal = _strip_inline_references(journal)

        # Save to library if enabled
        if req.library:
            paper_titles = [getattr(p, "title", "") or "" for p in papers]
            work = WorkRecord(
                work_id=str(uuid.uuid4()),
                theme=req.theme,
                content=journal,
                language=req.language,
                mode=req.mode or "journal",
                provider=provider.display_name,
                paper_titles=paper_titles,
            )
            works_store.save_work(work)
            print(f"[Librarian] Saved work '{work.work_id[:8]}'")
    except Exception as e:
        print(f"[Librarian] Save error: {e}")

    return GenerateResponse(journal=journal, provider_used=provider.display_name, token_usage=token_usage)


@app.post("/api/generate/stream")


@app.post("/api/generate/stream")
async def generate_journal_stream(req: GenerateRequest):
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

    if req.research_job_id:
        from .research import get_job as get_research_job
        research_job = get_research_job(req.research_job_id)
        if research_job and research_job.sources:
            for src in research_job.sources:
                if not src.text:
                    continue
                papers.append(Paper(
                    title=src.title,
                    abstract=src.text[:1000],
                    authors=[],
                    year=None,
                    doi=None,
                    openalex_url=None,
                    url=src.url,
                    pdf_url=None,
                    source=f"research_{src.source}",
                    cited_by_count=0,
                ))

    # RAG: scrape PDFs and index chunks (persistent)
    paper_ids = "-".join(sorted(p.doi or p.openalex_url or p.title for p in papers))
    paper_hash = hashlib.md5(paper_ids.encode()).hexdigest()
    await _setup_rag(papers, paper_hash)

    template = None
    if req.template_id:
        template = load_template(req.template_id)

    log_queue: asyncio.Queue = asyncio.Queue()

    # Librarian: search previous works for context
    prev_works_ctx = ""
    if req.library:
        similar = works_store.search_similar(req.theme, top_k=3, min_score=0.05)
        if similar:
            prev_works_ctx = format_previous_works_context(similar)
            print(f"[Librarian] Found {len(similar)} similar past works")

    async def event_stream() -> AsyncGenerator[str, None]:
        generation_task = asyncio.create_task(_run_generation(
            provider=provider, papers=papers, theme=req.theme,
            language=req.language, target_length=req.target_length,
            num_chapters=req.num_chapters, mode=req.mode,
            multi_agent=req.multi_agent, template=template,
            has_data=req.has_data, user_data=req.user_data,
            log_queue=log_queue,
            previous_works_ctx=prev_works_ctx,
            do_library=req.library,
        ))

        while True:
            try:
                entry = await asyncio.wait_for(log_queue.get(), timeout=1.0)
                yield f"data: {json.dumps(entry)}\n\n"
                if entry.get("type") == "result":
                    break
            except asyncio.TimeoutError:
                if generation_task.done():
                    break
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

        if generation_task.done() and not generation_task.cancelled():
            exc = generation_task.exception()
            if exc:
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _run_generation(
    provider, papers, theme, language, target_length, num_chapters,
    mode, multi_agent, template, has_data, user_data, log_queue,
    previous_works_ctx="", do_library=False,
):
    try:
        prev_ctx = previous_works_ctx

        if mode == "textbook":
            journal, token_usage = await generate_textbook(
                provider=provider, papers=papers, theme=theme,
                language=language, num_chapters=num_chapters,
                template=template, has_data=has_data, user_data=user_data,
                log_queue=log_queue, previous_works_ctx=prev_ctx,
            )
            token_usage["estimated"] = True
        elif multi_agent:
            journal, token_usage = await generate_multi_agent(
                provider=provider, papers=papers, theme=theme,
                language=language, target_length=target_length,
                template=template, has_data=has_data, user_data=user_data,
                log_queue=log_queue, previous_works_ctx=prev_ctx,
            )
            token_usage["estimated"] = True
        else:
            system_prompt = build_system_prompt(language)
            if prev_ctx:
                system_prompt = prev_ctx + "\n\n" + system_prompt
            num_parts = count_parts(target_length)
            journal_parts = []
            previous_content = None
            for part in range(1, num_parts + 1):
                section_queries = {
                    1: f"{theme} introduction background literature review",
                    2: f"{theme} method findings results discussion",
                    3: f"{theme} conclusion implications",
                }
                query = section_queries.get(part, theme)
                rag_results = store.search(query, top_k=5, min_score=0.05)
                rag_context = store.format_context(rag_results, papers) if rag_results else None

                prompt = build_part_prompt(
                    papers, language, theme, target_length,
                    part=part, num_parts=num_parts, previous_content=previous_content,
                    rag_context=rag_context, has_data=has_data, user_data=user_data,
                )
                part_text = await provider.generate(prompt, system_prompt=system_prompt)

                if part != num_parts:
                    for marker in ["\n## References", "\nReferences", "\n## Daftar Pustaka", "\nDaftar Pustaka"]:
                        idx = part_text.find(marker)
                        if idx != -1:
                            part_text = part_text[:idx]
                if part > 1:
                    new_sections = (
                        ["## Metode Penelitian", "## Temuan dan Pembahasan", "## Research Method", "## Findings and Discussion"]
                        if part == 2 else ["## Penutup", "## Conclusion"]
                    )
                    for s in new_sections:
                        idx = part_text.find(s)
                        if idx != -1:
                            part_text = part_text[idx:]
                            break
                journal_parts.append(part_text)
                previous_content = (previous_content or "") + "\n\n" + part_text
            journal = "\n\n".join(journal_parts)
            token_usage = None

        import time
        t = time.time()

        # Skip matplotlib entirely if no diagram blocks
        if "---DIAGRAM---" not in journal:
            print("[PostProcess] No diagram blocks, skipping matplotlib")
        else:
            print("[PostProcess] Rendering diagrams (matplotlib)...")
            try:
                # Run in thread pool with 60s timeout to avoid hanging
                loop = asyncio.get_event_loop()
                journal = await asyncio.wait_for(
                    loop.run_in_executor(None, extract_and_render_diagrams, journal),
                    timeout=60,
                )
                print(f"[PostProcess] matplotlib diagrams done ({time.time()-t:.1f}s)")
            except asyncio.TimeoutError:
                print("[PostProcess] matplotlib timed out (60s) — skipping diagram rendering")
                # Remove raw diagram blocks from output
                journal = re.sub(
                    r"---DIAGRAM---\s*\n.*?---END DIAGRAM---\s*\n?",
                    "", journal, flags=re.DOTALL
                )

        t2 = time.time()
        print("[PostProcess] Rendering mermaid...")
        journal = await render_diagrams(journal)
        print(f"[PostProcess] mermaid done ({time.time()-t2:.1f}s)")
        journal = replace_references(journal, papers, language)
        journal = _strip_inline_references(journal)

        print("[PostProcess] Sending result to frontend...")

        # Save to library if enabled
        if do_library:
            paper_titles = [getattr(p, "title", "") or p.get("title", "") for p in papers]
            work = WorkRecord(
                work_id=str(uuid.uuid4()),
                theme=theme,
                content=journal,
                language=language,
                mode=mode or "journal",
                provider=provider.display_name,
                paper_titles=paper_titles,
            )
            works_store.save_work(work)
            await log_queue.put({
                "type": "log", "agent": "Librarian",
                "message": f"Karya disimpan ke perpustakaan ({work.work_id[:8]})",
                "detail": f"Tema: {theme}",
            })

        await log_queue.put({
            "type": "result",
            "journal": journal,
            "provider_used": provider.display_name,
            "token_usage": token_usage,
        })
    except Exception as e:
        await log_queue.put({"type": "error", "message": str(e)})


@app.post("/api/restructure/parse", response_model=RestructureParseResponse)
async def parse_restructure_source(file: Optional[UploadFile] = File(None), file_url: Optional[str] = None):
    if file:
        raw = await file.read()
        # Try to extract text based on extension
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext in (".pdf", ".docx"):
            import tempfile
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            try:
                tmp.write(raw)
                tmp.close()
                text = parse_upload(tmp.name) or ""
            finally:
                os.unlink(tmp.name)
        else:
            text = raw.decode("utf-8", errors="replace")
    elif file_url:
        result = await resolve_link(file_url)
        if not result:
            raise HTTPException(status_code=400, detail="Could not resolve link or download file")
        text = result["text"]
        if result["ext"] in (".pdf", ".docx"):
            import tempfile
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=result["ext"])
            try:
                tmp.write(text.encode("utf-8"))
                tmp.close()
                parsed = parse_upload(tmp.name)
                text = parsed or text
            finally:
                os.unlink(tmp.name)
    else:
        raise HTTPException(status_code=400, detail="Provide a file or a Google Drive/Docs link")

    parsed = parse_document(text)
    return RestructureParseResponse(
        source_text=text,
        headings=parsed["headings"],
        sections=parsed["sections"],
        has_markdown_headings=parsed["has_markdown_headings"],
    )


@app.post("/api/restructure", response_model=RestructureResponse)
async def restructure_source(req: RestructureRequest):
    if not req.source_text.strip():
        raise HTTPException(status_code=400, detail="source_text is required")
    template = load_template(req.template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{req.template_id}' not found")

    provider_kwargs = {}
    if req.provider_model:
        provider_kwargs["model"] = req.provider_model
    if req.api_key:
        provider_kwargs["api_key"] = req.api_key
    if req.provider_base_url:
        provider_kwargs["base_url"] = req.provider_base_url

    provider = get_provider(req.provider, **provider_kwargs)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Provider '{req.provider}' not available")

    try:
        restructured, token_usage = await restructure_doc(
            provider=provider,
            source_text=req.source_text,
            template=template,
            lang=req.language,
            theme=req.theme,
            has_data=req.has_data,
            user_data=req.user_data,
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"LLM provider '{req.provider}' not reachable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restructure failed: {e}")

    restructured = _strip_inline_references(restructured)

    return RestructureResponse(
        restructured_text=restructured,
        provider_used=provider.display_name,
        token_usage=token_usage,
    )


_revise_prompt_id = """Anda adalah asisten akademik yang membantu merevisi dokumen berdasarkan review dari manusia.

DOKUMEN ASLI:
{source_text}

REVIEW / FEEDBACK DARI REVIEWER:
{review_text}

TUGAS ANDA:
1. Baca dan pahami setiap poin review dengan seksama.
2. Revisi dokumen asli dengan mengakomodasi SEMUA feedback dari reviewer.
3. Pertahankan struktur dan gaya penulisan asli — jangan ubah bagian yang tidak direview.
4. Jika reviewer meminta tambahan konten, tambahkan dengan gaya yang konsisten.
5. PENTING: HANYA gunakan sitasi inline (Penulis, Tahun). JANGAN cantumkan judul jurnal, volume, DOI, atau URL di badan dokumen.
6. Outputkan SELURUH dokumen yang sudah direvisi, bukan hanya bagian yang berubah.
7. JANGAN tambahkan komentar atau penjelasan di luar konten dokumen."""

_revise_prompt_en = """You are an academic assistant that revises documents based on human reviewer feedback.

ORIGINAL DOCUMENT:
{source_text}

REVIEWER FEEDBACK:
{review_text}

YOUR TASK:
1. Carefully read and understand every review point.
2. Revise the original document addressing ALL reviewer feedback.
3. Preserve the original structure and writing style — do not change sections not mentioned in the review.
4. If the reviewer requests additional content, add it in a consistent style.
5. IMPORTANT: Only use inline citations (Author, Year). Do NOT include journal name, volume, DOI, or URLs in the document body.
6. Output the ENTIRE revised document, not just the changed sections.
7. Do NOT add commentary or explanations outside the document content."""


def _build_revise_prompt(source_text: str, review_text: str, lang: str) -> str:
    tmpl = _revise_prompt_id if lang == "id" else _revise_prompt_en
    return tmpl.format(source_text=source_text, review_text=review_text)


@app.post("/api/revise/parse", response_model=ReviseParseResponse)
async def parse_reviewed_document(file: Optional[UploadFile] = File(None), file_url: Optional[str] = Form(None)):
    if not file and not file_url:
        raise HTTPException(status_code=400, detail="Provide a file or a link")

    # Handle Google Docs / Drive link (no file)
    if file_url and (not file or not file.filename):
        try:
            resolved = await resolve_link(file_url)
            if not resolved:
                raise HTTPException(status_code=400, detail="Could not resolve link")
            return ReviseParseResponse(source_text=resolved["text"], review_text="", comment_count=0)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch from link: {e}")

    # Handle .docx file (with or without link)
    if not file or not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")

    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        doc = DocxDocument(tmp_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        source_text = "\n\n".join(paragraphs)

        review_parts = []
        for comment in doc.comments:
            author = comment.author or "Reviewer"
            review_parts.append(f"{author}: {comment.text}")
        review_text = "\n\n".join(review_parts) if review_parts else ""

        os.unlink(tmp_path)
        return ReviseParseResponse(source_text=source_text, review_text=review_text, comment_count=len(review_parts))
    except Exception as e:
        if 'tmp_path' in locals(): os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail=f"Failed to parse .docx: {e}")


REVISE_CHUNK_MAX = 3000


def _build_chunk_revise_prompt(
    chunk: str,
    chunk_idx: int,
    total_chunks: int,
    review_text: str,
    lang: str,
) -> str:
    pos = f"Chunk {chunk_idx + 1} of {total_chunks}"
    if lang == "id":
        return f"""Anda membantu merevisi dokumen berdasarkan review dari manusia.

BAGIAN DOKUMEN ({pos}):
{chunk}

REVIEW / FEEDBACK YANG RELEVAN:
{review_text}

TUGAS:
1. Revisi bagian dokumen di atas berdasarkan feedback yang relevan.
2. Pertahankan gaya penulisan asli — jangan ubah bagian yang tidak disebut di review.
3. Output ONLY bagian yang sudah direvisi, tanpa komentar tambahan."""
    else:
        return f"""You are helping revise a document based on human reviewer feedback.

DOCUMENT PART ({pos}):
{chunk}

RELEVANT REVIEW FEEDBACK:
{review_text}

TASK:
1. Revise the document part above based on relevant feedback.
2. Preserve original writing style — do not change parts not mentioned in the review.
3. Output ONLY the revised part, no extra commentary."""


@app.post("/api/revise", response_model=ReviseResponse)
async def revise_document(req: ReviseRequest):
    provider_kwargs = {}
    if req.provider_model:
        provider_kwargs["model"] = req.provider_model
    if req.api_key:
        provider_kwargs["api_key"] = req.api_key
    if req.provider_base_url:
        provider_kwargs["base_url"] = req.provider_base_url
    provider = get_provider(req.provider, **provider_kwargs)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Provider '{req.provider}' not available")

    system = (
        "Anda adalah asisten akademik yang ahli merevisi dokumen. Anda selalu mempertahankan konten asli "
        "dan hanya mengubah bagian yang diminta reviewer."
        if req.language == "id"
        else "You are an academic assistant skilled at revising documents. You always preserve original "
        "content and only change sections requested by the reviewer."
    )

    try:
        source = req.source_text
        review_text = req.review_text

        if len(source) <= REVISE_CHUNK_MAX:
            prompt = _build_revise_prompt(source, review_text, req.language)
            revised = await provider.generate(prompt, system_prompt=system)
            token_usage = {
                "input_tokens": max(1, len(prompt) // 4),
                "output_tokens": max(1, len(revised) // 4),
                "estimated": True,
            }
        else:
            from .rag.chunker import chunk_text
            chunks = chunk_text(source, chunk_size=REVISE_CHUNK_MAX, overlap=200)
            print(f"[Revise] Split into {len(chunks)} chunks")

            combined = []
            total_in = 0
            total_out = 0
            for i, chunk in enumerate(chunks):
                prompt = _build_chunk_revise_prompt(chunk, i, len(chunks), review_text, req.language)
                chunk_text = await provider.generate(prompt, system_prompt=system)
                combined.append(chunk_text)
                total_in += max(1, len(prompt) // 4)
                total_out += max(1, len(chunk_text) // 4)
                print(f"[Revise] Chunk {i+1}/{len(chunks)} done")

            revised = "\n\n".join(combined)
            token_usage = {
                "input_tokens": total_in,
                "output_tokens": total_out,
                "estimated": True,
            }
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"LLM provider '{req.provider}' not reachable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Revise failed: {e}")

    revised = _strip_inline_references(revised)

    return ReviseResponse(
        revised_text=revised,
        provider_used=provider.display_name,
        token_usage=token_usage,
    )


TRANSLATE_CHUNK_MAX = 3000


def _build_translate_prompt(chunk: str, chunk_idx: int, total_chunks: int, src: str, tgt: str) -> str:
    pos = f"Chunk {chunk_idx + 1} of {total_chunks}"
    dir_label = f"{src} → {tgt}"
    preserve = (
        "- ## headings and markdown structure\n"
        "- Inline citations like (Author, Year) or [Author, Year] — DO NOT translate names\n"
        "- Markdown tables |---|---|\n"
        "- ---DIAGRAM--- ... ---END DIAGRAM--- blocks\n"
        "- ```mermaid ... ``` code blocks\n"
        "- URLs and DOIs\n"
    )
    return f"""Translate the following document part ({pos}) from {dir_label}.

RULES — preserve these EXACTLY as-is:
{preserve}
Translate ALL other text naturally. Academic terminology must be accurate.

DOCUMENT PART:
{chunk}

TRANSLATED TEXT:"""


@app.post("/api/translate", response_model=TranslateResponse)
async def translate_document(req: TranslateRequest):
    provider_kwargs = {}
    if req.provider_model:
        provider_kwargs["model"] = req.provider_model
    if req.api_key:
        provider_kwargs["api_key"] = req.api_key
    if req.provider_base_url:
        provider_kwargs["base_url"] = req.provider_base_url
    provider = get_provider(req.provider, **provider_kwargs)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Provider '{req.provider}' not available")

    src = "English" if req.source_language == "en" else "Indonesian"
    tgt = "English" if req.target_language == "en" else "Indonesian"
    system = (
        f"Anda adalah penerjemah akademik. Terjemahkan dari {src} ke {tgt}. "
        f"Pertahankan struktur markdown, heading, tabel, sitasi, dan blok diagram persis seperti aslinya. "
        f"Hanya ubah teks naratif."
        if req.target_language == "id"
        else f"You are an academic translator. Translate from {src} to {tgt}. "
        f"Preserve markdown structure, headings, tables, citations, and diagram blocks exactly. "
        f"Only translate narrative text."
    )

    try:
        source = req.source_text
        if len(source) <= TRANSLATE_CHUNK_MAX:
            text = source
            prompt = _build_translate_prompt(text, 0, 1, src, tgt)
            translated = await provider.generate(prompt, system_prompt=system)
            token_usage = {
                "input_tokens": max(1, len(prompt) // 4),
                "output_tokens": max(1, len(translated) // 4),
                "estimated": True,
            }
        else:
            from .rag.chunker import chunk_text
            chunks = chunk_text(source, chunk_size=TRANSLATE_CHUNK_MAX, overlap=200)
            print(f"[Translate] Split into {len(chunks)} chunks")

            combined = []
            total_in = 0
            total_out = 0
            for i, chunk in enumerate(chunks):
                prompt = _build_translate_prompt(chunk, i, len(chunks), src, tgt)
                chunk_text_res = await provider.generate(prompt, system_prompt=system)
                combined.append(chunk_text_res)
                total_in += max(1, len(prompt) // 4)
                total_out += max(1, len(chunk_text_res) // 4)
                print(f"[Translate] Chunk {i+1}/{len(chunks)} done")

            translated = "\n\n".join(combined)
            token_usage = {
                "input_tokens": total_in,
                "output_tokens": total_out,
                "estimated": True,
            }

        translated = _strip_inline_references(translated)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"LLM provider '{req.provider}' not reachable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translate failed: {e}")

    return TranslateResponse(
        translated_text=translated,
        provider_used=provider.display_name,
        token_usage=token_usage,
    )


@app.get("/api/templates")
async def get_templates():
    return list_templates()


@app.post("/api/templates")
async def create_template(data: dict):
    required = data.get("name", "").strip()
    if not required:
        raise HTTPException(status_code=400, detail="Template name is required")
    result = save_template(data)
    return result


@app.delete("/api/templates/{template_id}")
async def remove_template(template_id: str):
    ok = delete_template(template_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Template not found or is built-in")
    return {"status": "deleted"}


@app.post("/api/templates/parse")
async def parse_template_file(file: UploadFile = File(...)):
    if file.filename is None:
        raise HTTPException(status_code=400, detail="No file provided")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".pdf", ".docx", ".txt", ".md"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Supported: .pdf, .docx, .txt, .md")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()
        text = parse_upload(tmp.name)
        if not text:
            raise HTTPException(status_code=400, detail="Could not extract text from file")
    finally:
        os.unlink(tmp.name)

    # Try LLM to extract structure; fall back to heading detection
    from .restructure.parser import detect_all
    headings = detect_all(text)

    import json as _json
    for _provider_id in ["ollama", "openai", "anthropic", "gemini"]:
        try:
            provider = get_provider(_provider_id)
            if provider:
                parse_prompt = f"""You are given author guidelines for an academic journal or textbook.
Extract the required section structure, heading hierarchy, and any rules/constraints.

Output ONLY valid JSON with this structure:
{{
  "name": "suggested template name",
  "type": "journal" or "textbook",
  "sections": [
    {{"level": 2, "heading_id": "Nama Bagian (Indonesian)", "heading_en": "Section Name (English)"}},
    ...
  ],
  "constraints": {{
    "abstrak_maks": 150 or null,
    "kata_kunci_maks": 5 or null,
    "total_halaman_maks": null,
    "citation_style": "APA 7th" or null
  }},
  "chapter_subsections": [
    {{"level": 3, "heading_id": "Sub-bab (Indonesian)", "heading_en": "Subsection (English)"}},
    ...
  ]
}}

For "type": if this looks like a textbook guide, include chapter_subsections.
For journal type, include sections only.
Infer English translations where possible. If the text is only in Indonesian, guess reasonable English equivalents.
DO NOT include any text outside the JSON.

Guidelines text:
{text[:8000]}"""
                result = await provider.generate(parse_prompt)
                result = result.strip()
                if result.startswith("```"):
                    result = "\n".join(result.split("\n")[1:])
                if result.endswith("```"):
                    result = "\n".join(result.split("\n")[:-1])
                result = result.strip()
                parsed = _json.loads(result)
                return parsed
        except Exception:
            continue

    # Fallback: rule-based heading detection
    if headings:
        sections = [{"level": h["level"], "heading_id": h["heading"], "heading_en": h["heading"]} for h in headings]
        return {
            "name": "Extracted Template",
            "type": "journal",
            "sections": sections,
            "constraints": {},
        }

    raise HTTPException(status_code=422, detail="No headings detected and no LLM available to parse guidelines")


@app.get("/api/works", response_model=WorksListResponse)
async def list_works(limit: int = 50, offset: int = 0):
    works = works_store.list_works(limit=limit, offset=offset)
    return WorksListResponse(works=works, total=len(works))


@app.delete("/api/works/{work_id}", response_model=WorksDeleteResponse)
async def delete_work(work_id: str):
    if not work_id.strip():
        raise HTTPException(status_code=400, detail="work_id is required")
    ok = works_store.delete_work(work_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Work not found")
    return WorksDeleteResponse(status="deleted")


frontend_dir = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404)
    file_path = frontend_dir / full_path
    if file_path.is_file():
        return FileResponse(str(file_path))
    index = frontend_dir / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(status_code=404)
