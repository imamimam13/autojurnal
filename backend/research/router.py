import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from .pipeline import create_job, get_job, run_research

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchStartRequest(BaseModel):
    theme: str = ""
    title: str = ""
    language: str = "id"


class ResearchStartResponse(BaseModel):
    job_id: str
    status: str


class ResearchStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    progress_detail: str
    sources_count: int
    scraped_count: int
    error: Optional[str] = None


@router.post("/start", response_model=ResearchStartResponse)
async def start_research(req: ResearchStartRequest):
    job = create_job(theme=req.theme, title=req.title, language=req.language)
    asyncio.create_task(run_research(job))
    return ResearchStartResponse(job_id=job.job_id, status=job.status)


@router.get("/status/{job_id}", response_model=ResearchStatusResponse)
async def get_research_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Research job not found")
    scraped = sum(1 for s in job.sources if s.text)
    return ResearchStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        progress_detail=job.progress_detail,
        sources_count=len(job.sources),
        scraped_count=scraped,
        error=job.error,
    )
