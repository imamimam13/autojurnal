import re
from typing import Optional


def detect_headings(text: str) -> list[dict]:
    lines = text.split("\n")
    headings = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Markdown heading: ## ..., ### ...
        m = re.match(r"^(#{2,})\s+(.+)$", stripped)
        if m:
            headings.append({
                "level": len(m.group(1)),
                "heading": m.group(2).strip(),
                "line": i,
            })
    return headings


def split_sections(text: str) -> list[dict]:
    lines = text.split("\n")
    sections = []
    current = None
    current_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        m = re.match(r"^(#{2,})\s+(.+)$", stripped)
        if m:
            if current is not None:
                content_lines = lines[current_start:i]
                current["content"] = "\n".join(content_lines).strip()
                sections.append(current)
            current = {
                "level": len(m.group(1)),
                "heading": m.group(2).strip(),
                "content": "",
                "start_line": i,
            }
            current_start = i

    if current is not None:
        content_lines = lines[current_start:]
        current["content"] = "\n".join(content_lines).strip()
        sections.append(current)

    return sections


def detect_plain_text_headings(text: str) -> list[dict]:
    lines = text.split("\n")
    headings = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # All caps short line (possible heading)
        if len(stripped) < 120 and stripped == stripped.upper() and len(stripped) > 5:
            headings.append({
                "level": 2,
                "heading": stripped.title(),
                "line": i,
            })
            continue
        # Numbered: "1. Introduction" / "A. Background"
        m = re.match(r"^[A-Z0-9]+[\.\)]\s+(.+)$", stripped)
        if m and len(stripped) < 100:
            headings.append({
                "level": 2,
                "heading": m.group(1).strip(),
                "line": i,
            })
    return headings


def detect_all(text: str) -> list[dict]:
    md_headings = detect_headings(text)
    if len(md_headings) >= 2:
        return md_headings
    # Fallback: try plain text detection
    return detect_plain_text_headings(text)


def parse_document(text: str) -> dict:
    sections = split_sections(text)
    headings = detect_all(text)
    return {
        "text": text,
        "headings": headings,
        "sections": sections,
        "has_markdown_headings": len(detect_headings(text)) >= 2,
    }
