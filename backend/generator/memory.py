import re
from typing import Optional, List, Dict


class RollingMemory:
    """
    Manages working memory across multiple sections or chapters in multi-agent and textbook generation.
    Maintains a rolling window of recent sections in full detail while compacting older sections
    into an executive carry-over digest to stay strictly within context/memory limits.
    """

    def __init__(self, max_recent: int = 2, max_chars: int = 5000, lang: str = "id"):
        self.max_recent = max_recent
        self.max_chars = max_chars
        self.lang = lang
        self.entries: List[Dict[str, str]] = []  # list of {"heading": str, "summary": str}

    def add(self, heading: str, summary: str):
        """Add a newly completed section/chapter summary to working memory."""
        cleaned_summary = summary.strip()
        # Clean heading if it has markdown prefix
        cleaned_heading = heading.replace("##", "").strip()
        self.entries.append({
            "heading": cleaned_heading,
            "summary": cleaned_summary,
        })

    def get_summary(self, max_chars: Optional[int] = None) -> str:
        """
        Builds a compact carry-over working memory string.
        If the memory is within budget, lists all summaries.
        If exceeding budget or max_recent, compacts older entries into an executive carryover block
        and retains the most recent entries in full detail.
        """
        if not self.entries:
            return ""

        budget = max_chars or self.max_chars
        total_entries = len(self.entries)

        if total_entries <= self.max_recent:
            # All fit in recent window
            blocks = [f"### {e['heading']}\n{e['summary']}" for e in self.entries]
            result = "\n\n".join(blocks)
            if len(result) <= budget:
                return result
            # If still too long, trim individual summaries
            return self._trim_to_budget(blocks, budget)

        # Split into older entries (to carry over in condensed form) and recent entries
        older_entries = self.entries[:-self.max_recent]
        recent_entries = self.entries[-self.max_recent:]

        older_digest_lines = []
        for e in older_entries:
            # Extract bullet points or first 2 lines from older summary
            lines = [l.strip() for l in e["summary"].split("\n") if l.strip()]
            shortened = "; ".join(lines[:2]) if lines else "Telah dibahas."
            older_digest_lines.append(f"- **{e['heading']}**: {shortened}")

        if self.lang == "id":
            older_block = "### Ringkasan Bagian Terdahulu (Carry-Over):\n" + "\n".join(older_digest_lines)
        else:
            older_block = "### Previous Sections Digest (Carry-Over):\n" + "\n".join(older_digest_lines)

        recent_blocks = [f"### {e['heading']}\n{e['summary']}" for e in recent_entries]
        combined = older_block + "\n\n" + "\n\n".join(recent_blocks)

        if len(combined) <= budget:
            return combined

        # Emergency trim to budget if still exceeding
        return self._trim_to_budget([older_block] + recent_blocks, budget)

    def _trim_to_budget(self, blocks: List[str], budget: int) -> str:
        """Trims blocks backwards to ensure total characters fit within budget."""
        result = []
        current_len = 0
        # Preserve recent blocks from the end
        for b in reversed(blocks):
            if current_len + len(b) + 2 <= budget:
                result.insert(0, b)
                current_len += len(b) + 2
            else:
                remaining = budget - current_len - 10
                if remaining > 100:
                    truncated = b[:remaining] + "..."
                    result.insert(0, truncated)
                break
        return "\n\n".join(result)

    def __len__(self) -> int:
        return len(self.entries)


def compact_previous_content(previous_content: str, max_chars: int = 8000, lang: str = "id") -> str:
    """
    Compresses previous document content for standard multi-part generation (journal.py).
    If previous_content is within budget, returns as is.
    If it exceeds max_chars, extracts:
    1. Overall structure & headings
    2. Condensed beginning (e.g. Title/Abstract/Intro)
    3. Exact text of the final section / tail end (to maintain continuous writing flow)
    """
    if not previous_content or len(previous_content) <= max_chars:
        return previous_content or ""

    # Extract all headings to preserve context of structure
    headings = re.findall(r"^(##\s+[^\n]+)", previous_content, re.MULTILINE)
    structure_header = "Struktur yang sudah ditulis sebelumnya:" if lang == "id" else "Previously written structure:"
    structure_str = f"{structure_header}\n" + "\n".join(headings)

    # Keep the tail end (last ~3000 chars) for seamless writing continuity
    tail_chars = min(3500, max_chars // 2)
    tail_content = previous_content[-tail_chars:].strip()

    # Find the nearest clean heading or paragraph break in the tail
    first_heading_idx = tail_content.find("\n## ")
    if first_heading_idx != -1 and first_heading_idx < 1000:
        tail_content = tail_content[first_heading_idx:].strip()

    transition_note = (
        "\n\n[... Bagian terdahulu telah diringkas demi efisiensi konteks ...]\n\n"
        "AKHIR DARI BAGIAN SEBELUMNYA (Lanjutkan alur secara konsisten dari sini):\n"
        if lang == "id"
        else "\n\n[... Earlier sections condensed for context budget ...]\n\n"
        "END OF PRECEDING SECTION (Continue the narrative flow seamlessly from here):\n"
    )

    return f"{structure_str}\n\n{transition_note}\n{tail_content}"


def truncate_context_budget(text: Optional[str], max_chars: int = 4000, keep_tail: bool = False) -> str:
    """
    Safely truncates text blocks (e.g. RAG, user data, paper lists) to stay within token budgets.
    """
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    if keep_tail:
        return "... [konten awal diringkas] ...\n" + text[-max_chars:]
    return text[:max_chars] + "\n... [konten dipotong sesuai batas konteks]"


def is_context_overflow_error(error: Exception) -> bool:
    """
    Checks if an exception from any LLM provider (Ollama, Gemini, OpenAI, Anthropic, etc.)
    is caused by exceeding the context window length, token limits, or memory limits.
    """
    err_str = str(error).lower()
    keywords = [
        "context_length_exceeded",
        "context length",
        "context window",
        "maximum context",
        "max_tokens",
        "maximum tokens",
        "token limit",
        "too many tokens",
        "prompt is too long",
        "request is too large",
        "payload too large",
        "out of memory",
        "cuda out of memory",
        "oom",
        "string too long",
        "413",
        "400",
        "rate_limit_exceeded",
        "exceeds maximum",
        "model maximum context",
        "context length is",
    ]
    return any(k in err_str for k in keywords)


def compress_prompt_for_retry(system_prompt: Optional[str], prompt: str, lang: str = "id") -> tuple[str, str]:
    """
    Emergency compression of system prompt and user task when a context overflow occurs,
    allowing an automatic retry to succeed.
    """
    sys_str = system_prompt or ""
    task_str = prompt or ""

    # Compress system prompt: keep first 1500 chars
    if len(sys_str) > 2000:
        sys_str = sys_str[:1800] + ("\n[Instruksi disesuaikan demi kapasitas konteks]" if lang == "id" else "\n[System instruction trimmed for context]")

    # Compress user prompt: truncate inner RAG/Memory blocks aggressively
    if len(task_str) > 6000:
        # Halve the length while preserving the head and instructions at the tail
        head = task_str[:3000]
        tail = task_str[-2500:]
        notice = "\n\n[... Konteks disederhanakan otomatis agar muat dalam memory model ...]\n\n" if lang == "id" else "\n\n[... Context automatically compacted for model memory ...]\n\n"
        task_str = head + notice + tail

    return sys_str, task_str
