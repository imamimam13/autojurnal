import httpx
from typing import Optional
from dataclasses import dataclass, field
from config import settings


@dataclass
class Paper:
    title: str
    abstract: Optional[str]
    authors: list[str]
    year: Optional[int]
    doi: Optional[str]
    openalex_url: Optional[str]
    url: Optional[str]
    pdf_url: Optional[str]
    source: Optional[str]
    cited_by_count: int
    relevance_score: Optional[float] = None
    concepts: list[str] = field(default_factory=list)


class OpenAlexSearcher:
    BASE_URL = "https://api.openalex.org/works"

    def __init__(self, max_results: int = 20, api_key: Optional[str] = None):
        self.max_results = max_results
        self.api_key = api_key or settings.openalex_api_key

    async def search(
        self,
        query: str,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
        min_relevance: float = 0.0,
    ) -> list[Paper]:
        params = {
            "search": query,
            "per_page": min(self.max_results * 3, 200),
            "sort": "relevance_score:desc",
            "select": "id,title,abstract_inverted_index,authorships,publication_year,doi,primary_location,cited_by_count,concepts",
        }

        filters = []
        if from_year:
            filters.append(f"from_publication_date:{from_year}-01-01")
        if to_year:
            filters.append(f"to_publication_date:{to_year}-12-31")
        if filters:
            params["filter"] = ",".join(filters)

        headers = {}
        if self.api_key:
            headers["api_key"] = self.api_key

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(self.BASE_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        papers = []
        for result in data.get("results", []):
            abstract = self._decode_abstract(
                result.get("abstract_inverted_index")
            )
            authors = [
                auth.get("author", {}).get("display_name", "Unknown")
                for auth in result.get("authorships", [])
            ]
            concepts = [
                c.get("display_name", "")
                for c in result.get("concepts", [])[:5]
            ]
            source = None
            paper_url = None
            pdf_url = None
            primary_loc = result.get("primary_location")
            if primary_loc:
                src = primary_loc.get("source")
                if src:
                    source = src.get("display_name")
                paper_url = primary_loc.get("landing_page_url")
                pdf_url = primary_loc.get("pdf_url")

            if not pdf_url:
                continue

            raw_doi = result.get("doi") or ""
            doi = None
            if raw_doi:
                cleaned = raw_doi.replace("https://doi.org/", "")
                if cleaned.startswith("10.") and "xxxx" not in cleaned.lower():
                    doi = cleaned

            paper = Paper(
                title=result.get("title") or "Untitled",
                abstract=abstract,
                authors=authors,
                year=result.get("publication_year"),
                doi=doi,
                openalex_url=result.get("id"),
                url=paper_url,
                pdf_url=pdf_url,
                source=source,
                cited_by_count=result.get("cited_by_count", 0),
                relevance_score=result.get("relevance_score"),
                concepts=concepts,
            )

            papers.append(paper)
            if len(papers) >= self.max_results:
                break

        return papers

    def _decode_abstract(self, inverted_index: Optional[dict]) -> Optional[str]:
        if not inverted_index:
            return None
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        return " ".join(word for _, word in word_positions)
