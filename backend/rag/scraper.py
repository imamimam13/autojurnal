import asyncio
import httpx
import fitz

from .chunker import chunk_text


async def scrape_pdf(pdf_url: str, timeout: int = 30) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(pdf_url)
            resp.raise_for_status()
        doc = fitz.open(stream=resp.content, filetype="pdf")
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text.strip() or None
    except Exception:
        return None


async def scrape_all(papers: list, max_concurrent: int = 5) -> dict[int, list[str]]:
    sem = asyncio.Semaphore(max_concurrent)

    async def _scrape_one(idx: int, url: str) -> tuple[int, str | None]:
        async with sem:
            text = await scrape_pdf(url)
            return idx, text

    tasks = []
    for idx, p in enumerate(papers):
        pdf_url = getattr(p, "pdf_url", None) or (isinstance(p, dict) and p.get("pdf_url"))
        if not pdf_url:
            continue
        tasks.append(_scrape_one(idx, pdf_url))

    results = {}
    for idx, text in await asyncio.gather(*tasks):
        if text:
            results[idx] = chunk_text(text)

    return results
