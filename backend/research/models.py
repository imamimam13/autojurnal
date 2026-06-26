import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScrapedSource:
    title: str
    url: str
    snippet: str
    text: str
    source: str  # "google", "scholar", "pubmed"
    scrape_duration: float = 0.0


@dataclass
class ResearchJob:
    job_id: str
    theme: str
    title: str
    language: str
    status: str = "pending"  # pending, searching, scraping, done, error
    progress: int = 0
    progress_detail: str = ""
    sources: list[ScrapedSource] = field(default_factory=list)
    error: Optional[str] = None
    created_at: float = 0.0
