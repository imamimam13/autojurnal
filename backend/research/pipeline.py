import asyncio
import time
import traceback
import uuid
from typing import Optional

from .models import ScrapedSource, ResearchJob
from .searcher import _CLOAK_AVAILABLE, search_sources_sync
from .scraper import extract_text_sync

if _CLOAK_AVAILABLE:
    from cloakbrowser import launch as cloak_launch

_jobs: dict[str, ResearchJob] = {}

MAX_SCRAPE = 3
JOB_TIMEOUT = 90


def create_job(theme: str, title: str, language: str) -> ResearchJob:
    job_id = uuid.uuid4().hex[:12]
    job = ResearchJob(
        job_id=job_id,
        theme=theme,
        title=title,
        language=language,
        created_at=time.time(),
    )
    _jobs[job_id] = job
    return job


def get_job(job_id: str) -> Optional[ResearchJob]:
    return _jobs.get(job_id)


async def run_research(job: ResearchJob):
    query = job.title or job.theme
    if not query:
        job.status = "error"
        job.error = "No theme or title provided"
        return

    loop = asyncio.get_event_loop()
    all_sources: list[dict] = []
    browser = None

    try:
        # Phase 0: Launch browser once if available
        job.status = "searching"
        job.progress = 5
        job.progress_detail = "Searching..." if not _CLOAK_AVAILABLE else "Launching browser..."
        print(f"[Research] Starting: {query} (CloakBrowser: {_CLOAK_AVAILABLE})")

        if _CLOAK_AVAILABLE:
            browser = await loop.run_in_executor(None, lambda: cloak_launch())
        else:
            print("[Research] Using httpx-only mode (no Chromium binary)")

        # Phase 1: Search all 3 sources using shared browser
        job.progress = 10
        job.progress_detail = "Searching Google, Scholar, PubMed..."
        print(f"[Research] Searching all sources: {query}")

        sources = await loop.run_in_executor(
            None, lambda: search_sources_sync(query, browser, max_results=5),
        )

        for name, results in sources.items():
            for r in results:
                all_sources.append({**r, "source": name})
            print(f"[Research] {name}: {len(results)} results")
            job.progress_detail = f"Searching {name}... {len(results)} found"

        # Deduplicate by URL
        seen = set()
        unique_sources = []
        for src in all_sources:
            if src["url"] and src["url"] not in seen:
                seen.add(src["url"])
                unique_sources.append(src)

        if not unique_sources:
            job.status = "done"
            job.progress = 100
            job.progress_detail = "No sources found (all searches returned empty)"
            print(f"[Research] No sources found for: {query}")
            return

        # Phase 2: Scrape top articles (reuse same browser)
        job.status = "scraping"
        to_scrape = unique_sources[:MAX_SCRAPE]
        print(f"[Research] Scraping {len(to_scrape)} articles...")

        for i, src in enumerate(to_scrape):
            job.progress = 15 + int((i + 1) / len(to_scrape) * 75)
            job.progress_detail = f"Scraping {i+1}/{len(to_scrape)}: {src['title'][:50]}..."
            print(f"[Research] Scrape [{i+1}/{len(to_scrape)}]: {src['url'][:80]}")

            start_t = time.time()
            if browser:
                page = browser.new_page()
                try:
                    text = await loop.run_in_executor(
                        None, extract_text_sync, page, src["url"], 20000,
                    )
                finally:
                    page.close()
            else:
                text = extract_text_sync(url=src["url"])

            src["text"] = text
            src["scrape_duration"] = time.time() - start_t

        # Phase 3: Store results
        for src in unique_sources:
            job.sources.append(ScrapedSource(
                title=src.get("title", "Untitled"),
                url=src.get("url", ""),
                snippet=src.get("snippet", ""),
                text=src.get("text", ""),
                source=src.get("source", ""),
                scrape_duration=src.get("scrape_duration", 0.0),
            ))

        scraped_count = sum(1 for s in job.sources if s.text)
        job.status = "done"
        job.progress = 100
        job.progress_detail = f"Found {len(unique_sources)} sources, {scraped_count} with content"
        print(f"[Research] Done: {len(unique_sources)} sources total, {scraped_count} with content")

    except Exception as e:
        print(f"[Research] Fatal error: {e}\n{traceback.format_exc()}")
        job.status = "error"
        job.error = str(e)[:300]
    finally:
        if browser:
            try:
                await loop.run_in_executor(None, browser.close)
                print("[Research] Browser closed")
            except Exception as e:
                print(f"[Research] Browser close error: {e}")
