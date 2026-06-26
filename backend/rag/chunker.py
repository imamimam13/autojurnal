import re


# Patterns that indicate the start of references/bibliography
_REF_PATTERNS = re.compile(
    r"^\s*(?:daftar\s+pustaka|references?|bibliography|works\s+cited|"
    r"further\s+reading|(?:catatan\s+)?(?:akhir|penutup))\s*$",
    re.IGNORECASE,
)


def _trim_references(text: str) -> str:
    lines = text.split("\n")
    cut = len(lines)
    for i, line in enumerate(lines):
        if _REF_PATTERNS.match(line.strip()):
            cut = i
            break
    return "\n".join(lines[:cut]).strip()


def _truncate_to_sentence_end(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    cut = text.rfind(". ", 0, max_len)
    if cut == -1:
        cut = text.rfind(".\n", 0, max_len)
    if cut == -1:
        cut = text.rfind("\n", 0, max_len)
    if cut == -1:
        cut = max_len
    return text[: cut + 1].strip()


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    text = _trim_references(text)
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para or len(para) < 20:
            continue
        para_len = len(para)
        if para_len > chunk_size:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            pos = 0
            while pos < para_len:
                chunk = _truncate_to_sentence_end(para[pos:], chunk_size)
                if not chunk:
                    break
                chunks.append(chunk)
                advance = len(chunk) - overlap
                if advance <= 0:
                    break
                pos += advance
        elif current_len + para_len > chunk_size:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = para_len
        else:
            current.append(para)
            current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return [c for c in chunks if len(c) >= 20]
