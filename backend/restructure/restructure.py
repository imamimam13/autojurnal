import re
import base64
from typing import Optional
import httpx
from search.openalex import Paper
from providers.base import LLMProvider
from .parser import split_sections, detect_all


DIAGRAM_PLACEHOLDER = "<!-- mermaid:%s -->"


def _format_template_sections(template: dict, lang: str) -> str:
    sections = template.get("sections", [])
    if not sections:
        return ""
    items = []
    for s in sections:
        heading = s.get(f"heading_{lang}", s.get("heading_id", ""))
        if heading:
            items.append(f"- {heading}")
    header = "TARGET TEMPLATE (sections to follow in order):" if lang == "id" else "TARGET TEMPLATE (sections to follow in order):"
    return f"\n{header}\n" + "\n".join(items)


def _format_source_sections(sections: list[dict]) -> str:
    parts = []
    for s in sections:
        heading = s.get("heading", "?")
        level = s.get("level", 2)
        parts.append(f"{'#' * level} {heading}")
    return "\n".join(parts)


def build_restructure_prompt(
    source_text: str,
    source_sections: list[dict],
    template: dict,
    lang: str,
    theme: str = "",
    has_data: bool = False,
    user_data: Optional[str] = None,
) -> str:
    from diagrams.prompts import diagram_instruction

    source_headings_str = _format_source_sections(source_sections)
    target_str = _format_template_sections(template, lang)
    diag = diagram_instruction(has_data, lang, user_data)

    constraints = template.get("constraints") or {}
    constraint_lines = []
    if constraints.get("abstrak_maks"):
        constraint_lines.append(f"- Abstract max {constraints['abstrak_maks']} words")
    if constraints.get("kata_kunci_maks"):
        constraint_lines.append(f"- Max {constraints['kata_kunci_maks']} keywords")
    if constraints.get("citation_style"):
        constraint_lines.append(f"- Citation style: {constraints['citation_style']}")
    constraint_block = "\n" + "\n".join(constraint_lines) if constraint_lines else ""

    no_ref = (
        "\n\nPENTING: HANYA gunakan sitasi inline (Penulis, Tahun). "
        "JANGAN pernah mencantumkan judul jurnal, volume, nomor, halaman, DOI, atau URL di badan dokumen. "
        "Referensi lengkap hanya di bagian Daftar Pustaka."
        if lang == "id"
        else "\n\nIMPORTANT: Only use inline citations (Author, Year). "
        "NEVER include journal name, volume, issue, pages, DOI, or URLs in the document body. "
        "Full references belong only in the References section."
    )

    if lang == "id":
        return f"""Anda diberikan konten dari dokumen akademik yang sudah ada dan struktur template target.

SUMBER KONTEN (heading asli dipertahankan):
{source_text}

HEADING YANG TERDETEKSI DI SUMBER:
{source_headings_str}

TARGET TEMPLATE (harus mengikuti urutan ini):
{target_str}{constraint_block}

TUGAS ANDA:
1. Atur ulang konten sumber agar mengikuti struktur template target.
2. Untuk setiap section template: jika ada konten yang cocok di sumber → pindahkan UTUH (copy paste).
3. Jika hanya cocok sebagian → tulis ulang berdasarkan informasi dari sumber SAJA.
4. Jika TIDAK ADA konten yang cocok sama sekali → tulis: "[Konten tidak tersedia di sumber]"
5. JANGAN PERNAH membuat data, klaim, atau sitasi palsu.
6. Pertahankan SEMUA sitasi inline (Penulis, Tahun) dari sumber.
7. Gunakan heading ## untuk section level 2, ### untuk level 3.
8. Gunakan tabel Markdown untuk perbandingan data.{diag}{no_ref}
9. Output ONLY dokumen yang sudah direstruktur, tanpa komentar tambahan."""
    else:
        return f"""You are given source content from an existing academic document and a target template structure.

SOURCE CONTENT (original headings preserved):
{source_text}

DETECTED HEADINGS IN SOURCE:
{source_headings_str}

TARGET TEMPLATE (must follow this order):
{target_str}{constraint_block}

YOUR TASK:
1. Reorganize the source content to match the target template structure.
2. For each target section: if matching content exists in source → move it AS-IS (copy).
3. If partial match → rewrite using ONLY information from the source.
4. If NO matching content exists → write: "[Content not available in source]"
5. NEVER fabricate data, claims, or citations.
6. Preserve ALL inline citations (Author, Year) from the source.
7. Use ## headings for level 2, ### for level 3.
8. Use Markdown tables for data comparison.{diag}{no_ref}
9. Output ONLY the restructured document, no extra commentary."""


CHUNK_MAX = 3000
TRUNC_WARNING_ID = "\n\n> **Catatan:** Konten sumber dipotong karena terlalu panjang. Beberapa detail mungkin hilang."
TRUNC_WARNING_EN = "\n\n> **Note:** Source content was truncated due to length. Some details may be missing."


def _build_chunk_restructure_prompt(
    chunk: str,
    chunk_idx: int,
    total_chunks: int,
    template: dict,
    lang: str,
    source_sections: list[dict],
) -> str:
    from diagrams.prompts import diagram_instruction

    target_str = _format_template_sections(template, lang)
    constraints = template.get("constraints") or {}
    constraint_lines = []
    if constraints.get("abstrak_maks"):
        constraint_lines.append(f"- Abstract max {constraints['abstrak_maks']} words")
    if constraints.get("kata_kunci_maks"):
        constraint_lines.append(f"- Max {constraints['kata_kunci_maks']} keywords")
    if constraints.get("citation_style"):
        constraint_lines.append(f"- Citation style: {constraints['citation_style']}")
    constraint_block = "\n" + "\n".join(constraint_lines) if constraint_lines else ""
    diag = diagram_instruction(False, lang)

    no_ref = (
        "\n\nPENTING: HANYA gunakan sitasi inline (Penulis, Tahun). "
        "JANGAN pernah mencantumkan judul jurnal, volume, nomor, halaman, DOI, atau URL."
        if lang == "id"
        else "\n\nIMPORTANT: Only use inline citations (Author, Year). "
        "NEVER include journal name, volume, issue, pages, DOI, or URLs."
    )
    pos_info = f"Chunk {chunk_idx + 1} of {total_chunks}"
    if lang == "id":
        return f"""Anda diberikan BAGIAN dari konten dokumen akademik ({pos_info}) dan template target.

BAGIAN KONTEN:
{chunk}

TARGET TEMPLATE:
{target_str}{constraint_block}

TUGAS ANDA:
1. Kelompokkan konten di atas ke dalam section yang sesuai dari template.
2. Output HANYA konten yang relevan — gunakan heading template (## untuk level 2, ### untuk level 3).
3. Jika tidak ada konten yang cocok untuk suatu section, SKIP section tersebut.
4. JANGAN membuat data palsu. Pertahankan sitasi inline.{no_ref}
5. Output ONLY konten yang sudah dikelompokkan per section, tanpa komentar.{diag}"""
    else:
        return f"""You are given a PART of an academic document ({pos_info}) and a target template.

CONTENT PART:
{chunk}

TARGET TEMPLATE:
{target_str}{constraint_block}

YOUR TASK:
1. Group the content above into the appropriate template sections.
2. Output ONLY relevant content using template headings (## for level 2, ### for level 3).
3. If no content matches a section, SKIP that section.
4. Do NOT fabricate data. Preserve inline citations.{no_ref}
5. Output ONLY the content grouped by section, no commentary.{diag}"""


async def restructure_document(
    provider: LLMProvider,
    source_text: str,
    template: dict,
    lang: str = "id",
    theme: str = "",
    has_data: bool = False,
    user_data: Optional[str] = None,
) -> tuple[str, Optional[dict]]:
    from rag.chunker import chunk_text

    text = source_text

    sections = split_sections(text)

    # For small texts, process in one shot
    if len(text) <= CHUNK_MAX:
        prompt = build_restructure_prompt(text, sections, template, lang, theme, has_data, user_data)
        system_prompt = (
            "Anda adalah asisten akademik yang ahli dalam merestruktur dokumen. "
            "Anda selalu mempertahankan konten asli dan tidak pernah membuat informasi palsu."
            if lang == "id"
            else "You are an academic assistant skilled in document restructuring. "
            "You always preserve original content and never fabricate information."
        )
        result, token_usage = await _single_restructure(provider, prompt, system_prompt)
    else:
        # Chunk and process each chunk independently
        print(f"[Restructure] Pre-chunk text length: {len(text)} chars, CHUNK_MAX={CHUNK_MAX}")
        start_t = __import__('time').time()
        chunks = chunk_text(text, chunk_size=CHUNK_MAX, overlap=200)
        print(f"[Restructure] Chunking took {__import__('time').time()-start_t:.2f}s, "
              f"split into {len(chunks)} chunks (total chunk chars: {sum(len(c) for c in chunks)})")

        combined_parts = []
        total_in = 0
        total_out = 0
        system_prompt = (
            "Anda adalah asisten akademik yang ahli dalam merestruktur dokumen. "
            "Anda selalu mempertahankan konten asli dan tidak pernah membuat informasi palsu."
            if lang == "id"
            else "You are an academic assistant skilled in document restructuring. "
            "You always preserve original content and never fabricate information."
        )

        for i, chunk in enumerate(chunks):
            prompt = _build_chunk_restructure_prompt(chunk, i, len(chunks), template, lang, sections)
            result_text, usage = await _single_restructure(provider, prompt, system_prompt)
            combined_parts.append(result_text)
            total_in += usage.get("input_tokens", 0)
            total_out += usage.get("output_tokens", 0)
            print(f"[Restructure] Chunk {i+1}/{len(chunks)} done")

        result = "\n\n".join(combined_parts)
        token_usage = {
            "input_tokens": total_in,
            "output_tokens": total_out,
            "estimated": True,
        }

    # Render structured diagrams (---DIAGRAM--- blocks) via Python
    from diagrams import extract_and_render_diagrams
    result = extract_and_render_diagrams(result)
    # Render legacy mermaid blocks via Kroki
    result = await render_diagrams(result)

    return result, token_usage


async def _single_restructure(
    provider: LLMProvider,
    prompt: str,
    system_prompt: str,
) -> tuple[str, dict]:
    result = await provider.generate(prompt, system_prompt=system_prompt)
    token_usage = {
        "input_tokens": max(1, len(prompt) // 4),
        "output_tokens": max(1, len(result) // 4),
        "estimated": True,
    }
    return result, token_usage


async def render_diagrams(markdown_text: str) -> str:
    mermaid_blocks = re.findall(
        r"```mermaid\s*\n([\s\S]*?)```", markdown_text
    )
    if not mermaid_blocks:
        return markdown_text

    async with httpx.AsyncClient(timeout=15) as client:
        for i, code in enumerate(mermaid_blocks):
            try:
                resp = await client.post(
                    "https://kroki.io/mermaid/svg",
                    json={"diagram_source": code.strip(), "output_format": "svg"},
                )
                if resp.status_code == 200:
                    svg_b64 = base64.b64encode(resp.content).decode()
                    replacement = f"![Mermaid Diagram {i+1}](data:image/svg+xml;base64,{svg_b64})"
                    markdown_text = markdown_text.replace(
                        f"```mermaid\n{code}```", replacement, 1
                    )
                else:
                    print(f"[Diagram] Kroki error {resp.status_code} for block {i}")
            except Exception as e:
                print(f"[Diagram] Failed to render block {i}: {e}")

    return markdown_text
