import html as html_module
import re
import httpx
from typing import Optional


DRIVE_FILE_RE = re.compile(
    r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)"
)
DOCS_RE = re.compile(
    r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)"
)


def _extract_drive_id(url: str) -> Optional[str]:
    m = DRIVE_FILE_RE.search(url)
    return m.group(1) if m else None


def _extract_docs_id(url: str) -> Optional[str]:
    m = DOCS_RE.search(url)
    return m.group(1) if m else None


def _heading_to_markdown(html_text: str) -> str:
    """Convert HTML headings to Markdown headings, strip remaining tags."""
    body_match = re.search(r'<body[^>]*>(.*?)</body>', html_text, re.DOTALL | re.IGNORECASE)
    if body_match:
        html_text = body_match.group(1)

    for level in range(6, 0, -1):
        html_text = re.sub(
            rf'<h{level}[^>]*>(.*?)</h{level}>',
            lambda m, lvl=level: '\n' + '#' * lvl + ' ' + re.sub(r'<[^>]+>', '', m.group(1)).strip() + '\n',
            html_text,
            flags=re.DOTALL | re.IGNORECASE,
        )

    html_text = re.sub(r'</p>', '\n\n', html_text, flags=re.IGNORECASE)
    html_text = re.sub(r'<br\s*/?>', '\n', html_text, flags=re.IGNORECASE)
    html_text = re.sub(r'<(?:div|li|tr|th|td)[^>]*>', '\n', html_text, flags=re.IGNORECASE)
    html_text = re.sub(r'</(?:div|li|tr|th|td)>', '\n', html_text, flags=re.IGNORECASE)

    text = re.sub(r'<[^>]+>', ' ', html_text)
    text = html_module.unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n[ \t]+', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


async def resolve_link(url: str) -> Optional[dict]:
    url = url.strip()

    # Google Docs → export as HTML, convert headings to markdown
    docs_id = _extract_docs_id(url)
    if docs_id:
        export_url = f"https://docs.google.com/document/d/{docs_id}/export?format=html"
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(export_url)
                if resp.status_code == 200:
                    text = _heading_to_markdown(resp.text)
                    if len(text) > 50:
                        return {
                            "filename": f"gdoc_{docs_id[:8]}.txt",
                            "content": text.encode("utf-8"),
                            "ext": ".txt",
                        }
        except Exception as e:
            print(f"[GDrive] Docs export failed: {e}")

    # Google Drive file → download
    drive_id = _extract_drive_id(url)
    if not drive_id:
        return None

    download_url = f"https://drive.google.com/uc?export=download&id={drive_id}"
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(download_url)
            if resp.status_code != 200:
                return None
            content = resp.content
            # Try to detect if it's a PDF from content-type
            ct = resp.headers.get("content-type", "")
            ext = ".txt"
            if "pdf" in ct:
                ext = ".pdf"
            elif "word" in ct or "docx" in ct:
                ext = ".docx"
            return {
                "filename": f"gdrive_{drive_id[:8]}{ext}",
                "content": content,
                "ext": ext,
            }
    except Exception as e:
        print(f"[GDrive] Download failed: {e}")
        return None
