from typing import Optional
from ..search.openalex import Paper


BASE_TEMPLATE_EN = """Write an ORIGINAL qualitative research journal article on the given theme. The papers below are your REFERENCES — cite them as sources, but write EVERYTHING in your own original words and sentence structures.

CRITICAL — ORIGINAL WRITING ONLY:
- Every sentence must be originally constructed with your own phrasing and structure.
- Do NOT copy or closely follow the wording, structure, or key phrases from any paper's abstract.
- Write as if you are creating new knowledge and analysis, not summarizing existing papers.
- After writing, each sentence should look like YOU wrote it, not like a rewritten abstract.

IMPORTANT CITATION RULES:
1. Every claim or finding MUST be supported by an inline parenthetical citation in APA format: (Author, Year).
2. Cite papers as evidence for YOUR analysis — do not just list what each paper said.
3. Every paper listed MUST appear at least once as an inline citation.
4. The References section must list EVERY paper cited, sorted alphabetically.
5. Use the EXACT URL from the reference list — do NOT modify or fabricate DOIs/URLs.
6. Do NOT add volume, issue, pages, or other details not provided.
7. Format: Author (Year). Title. Source. URL: {{URL from list}}

LENGTH: {length_instruction}

PAPERS (reference list):
{paper_list}
"""

BASE_TEMPLATE_ID = """Tulislah ARTIKEL JURNAL KUALITATIF yang ORISINAL tentang tema yang diberikan. Paper-paper di bawah ini adalah REFERENSI Anda — sitasi sebagai sumber, tetapi tulis SEMUANYA dengan kata-kata dan struktur kalimat Anda sendiri yang orisinal.

KRITIS — HARUS TULISAN ORISINAL:
- Setiap kalimat harus dikonstruksi secara orisinal dengan frasa dan struktur Anda sendiri.
- JANGAN meniru atau mendekati kata-kata, struktur, atau frasa khas dari abstrak paper mana pun.
- Tulislah seolah Anda menciptakan pengetahuan dan analisis baru, bukan meringkas paper yang ada.
- Setelah selesai, setiap kalimat harus terlihat seperti tulisan ANDA, bukan seperti abstrak yang ditulis ulang.

ATURAN SITASI PENTING:
1. Setiap klaim atau temuan HARUS didukung oleh sitasi inline format APA: (Penulis, Tahun).
2. Sitasi paper sebagai bukti untuk ANALISIS ANDA — jangan sekadar mendaftar apa kata setiap paper.
3. Setiap paper dalam data HARUS muncul minimal sekali sebagai sitasi inline.
4. Daftar Pustaka harus mencantumkan SETIAP paper yang disitasi, urut alfabetis.
5. Gunakan URL yang TEPAT dari daftar referensi — JANGAN mengubah atau membuat-buat DOI/URL.
6. JANGAN membuat volume, nomor, halaman, atau informasi lain yang tidak tersedia.
7. Format tiap referensi: Penulis (Tahun). Judul. Sumber. URL: {{URL dari daftar}}

PANJANG: {length_instruction}

PAPER-PAPER (daftar referensi):
{paper_list}
"""

SECTIONS = {
    "en": {
        "part1": {
            "instruction": """Write ONLY the first part of the journal. Use ## headings, NOT numbered headings:
## Title
## Abstract
## Introduction
## Literature Review

Be extremely detailed. CRITICAL: Write everything in your own original words and structure. Do NOT use phrasing from paper abstracts. Use ONLY ## headings.""",
            "sections": ["Title", "Abstract", "Introduction", "Literature Review"],
        },
        "part2_medium": {
            "instruction": """Now write the SECOND and FINAL part. Use ## headings:
## Research Method
## Findings and Discussion
## Conclusion
## References

List ALL references sorted alphabetically. Use the EXACT URLs from the paper list — do NOT modify or fabricate DOIs. CRITICAL: Use ONLY ## headings.""",
            "sections": ["Research Method", "Findings and Discussion", "Conclusion", "References"],
        },
        "part2": {
            "instruction": """Now write the SECOND PART. Use ## headings:
## Research Method
## Findings and Discussion

Be extremely detailed. CRITICAL: Original writing only. Use ONLY ## headings.""",
            "sections": ["Research Method", "Findings and Discussion"],
        },
        "part3": {
            "instruction": """Now write the FINAL PART. Use ## headings:
## Conclusion
## References

List ALL references sorted alphabetically. Use the EXACT URLs from the paper list — do NOT fabricate DOIs.
NOTE: References are ADDITIONAL to the page target.""",
            "sections": ["Conclusion", "References"],
        },
    },
    "id": {
        "part1": {
            "instruction": """Tulis ONLY bagian PERTAMA dari jurnal. Gunakan heading ##, JANGAN heading bernomor:
## Judul
## Abstrak
## Pendahuluan
## Tinjauan Pustaka

Kembangkan sangat detail. KRITIS: Tulis dengan kata-kata dan struktur ANDA sendiri. Jangan pakai frasa dari abstrak. Gunakan ONLY heading ##.""",
            "sections": ["Judul", "Abstrak", "Pendahuluan", "Tinjauan Pustaka"],
        },
        "part2_medium": {
            "instruction": """Sekarang tulis bagian KEDUA dan TERAKHIR. Gunakan heading ##:
## Metode Penelitian
## Temuan dan Pembahasan
## Penutup
## Daftar Pustaka

Cantumkan SEMUA referensi urut alfabetis. Gunakan URL TEPAT dari daftar referensi — JANGAN membuat-buat DOI/URL palsu.
KRITIS: Tulisan orisinal — tidak boleh ada frasa pinjaman. Gunakan ONLY heading ##.""",
            "sections": ["Metode", "Temuan", "Penutup", "Daftar Pustaka"],
        },
        "part2": {
            "instruction": """Sekarang tulis bagian KEDUA dari jurnal. Gunakan heading ##:
## Metode Penelitian
## Temuan dan Pembahasan

Kembangkan sangat detail. KRITIS: Hanya tulisan orisinal. Gunakan ONLY heading ##.""",
            "sections": ["Metode Penelitian", "Temuan dan Pembahasan"],
        },
        "part3": {
            "instruction": """Sekarang tulis bagian AKHIR dari jurnal. Gunakan heading ##:
## Penutup
## Daftar Pustaka

Cantumkan SEMUA referensi urut alfabetis. Gunakan URL TEPAT dari daftar — JANGAN membuat DOI/URL palsu.
CATATAN: Daftar Pustaka di luar target halaman.""",
            "sections": ["Penutup", "Daftar Pustaka"],
        },
    },
}


def build_system_prompt(language: str) -> str:
    if language == "id":
        return "Anda adalah penulis jurnal akademik yang ahli dalam penelitian kualitatif. Anda selalu menulis dengan gaya akademik yang ketat, langsung pada intinya, dan tidak pernah menyapa pengguna atau membuat komentar di luar artikel."
    return "You are an expert academic writer specializing in qualitative research. You always write in strict academic style, get straight to the point, and never address the user or make meta-comments."


def build_paper_list(papers: list[Paper]) -> str:
    entries = []
    for i, p in enumerate(papers, 1):
        first_author = p.authors[0] if p.authors else "Unknown"
        if p.doi:
            url = f"https://doi.org/{p.doi}"
        elif p.url:
            url = p.url
        else:
            url = p.openalex_url or ""
        url_part = f" URL: {url}" if url else ""
        source_part = f" [{p.source}]" if p.source else ""
        entries.append(
            f"[{i}] {first_author} ({p.year}). {p.title}.{source_part}{url_part}"
        )
    return "\n".join(entries)


def get_length_info(target_length: str, language: str) -> dict:
    en = {
        "short": {"words": "1500-2000", "pages": "5-7", "detail": "Moderately detailed. ~5-7 pages of content (excluding references)."},
        "medium": {"words": "4000-6000", "pages": "12-18", "detail": "Comprehensive with in-depth analysis. ~12-18 pages of content (excluding references)."},
        "long": {"words": "8000-12000", "pages": "25-35", "detail": "Very comprehensive. ~25-35 pages of content (excluding references). Each section fully developed with deep analysis and extensive discussion."},
        "extended": {"words": "15000-25000", "pages": "45-60", "detail": "Extremely comprehensive. ~45-60 pages of content (excluding references). Multiple sub-sections, deep thematic analysis, synthesis tables."},
    }
    id_ = {
        "short": {"words": "1500-2000", "pages": "5-7", "detail": "Cukup detail. ~5-7 halaman konten (di luar daftar pustaka)."},
        "medium": {"words": "4000-6000", "pages": "12-18", "detail": "Komprehensif. ~12-18 halaman konten (di luar daftar pustaka). Analisis mendalam."},
        "long": {"words": "8000-12000", "pages": "25-35", "detail": "Sangat komprehensif. ~25-35 halaman konten (di luar daftar pustaka). Setiap bagian dikembangkan penuh dengan analisis mendalam."},
        "extended": {"words": "15000-25000", "pages": "45-60", "detail": "Ekstrem komprehensif. ~45-60 halaman konten (di luar daftar pustaka). Banyak sub-bagian, analisis tematik mendalam, tabel sintesis."},
    }
    return (id_ if language == "id" else en).get(target_length, en["medium"])


def count_parts(target_length: str) -> int:
    return {"short": 1, "medium": 2, "long": 3, "extended": 3}.get(target_length, 1)


def _per_part_words(total_words: str, num_parts: int, part: int) -> str:
    lo, hi = (int(s) for s in total_words.split("-"))
    total = (lo + hi) // 2
    per_part = total // num_parts
    margin = per_part // 3
    return f"{per_part - margin}-{per_part + margin}"


def build_part_prompt(
    papers: list[Paper],
    language: str,
    theme: str,
    target_length: str,
    part: int,
    num_parts: int = 1,
    previous_content: Optional[str] = None,
    rag_context: Optional[str] = None,
) -> str:
    template = BASE_TEMPLATE_ID if language == "id" else BASE_TEMPLATE_EN
    sections = SECTIONS["id" if language == "id" else "en"]
    lang_code = "id" if language == "id" else "en"
    info = get_length_info(target_length, language)
    part_words = _per_part_words(info["words"], num_parts, part)
    length_instruction = f"Write approximately {part_words} words for THIS PART. Be very detailed."

    theme_label = "Tema Penelitian" if language == "id" else "Research Theme"

    # Use part2_medium for 2-part medium mode
    if target_length == "medium" and part == 2:
        part_key = "part2_medium"
    else:
        part_key = f"part{part}"
    section_info = sections.get(part_key)
    if not section_info:
        raise ValueError(f"Invalid part number: {part}")

    rag_block = ""
    if rag_context:
        if language == "id":
            rag_block = (
                "\n\n---\n"
                "BERIKUT ADALAH KONTEN ASLI DARI PAPER YANG RELEVAN.\n"
                "Gunakan informasi di bawah ini sebagai SUMBER ANALISIS dan TEMUAN Anda.\n"
                "JANGAN pernah menyalin kalimat dari konten ini — bacalah, pahami, lalu tulis ulang dengan struktur kalimat dan kata-kata ANDA SENDIRI.\n"
                "Setiap fakta atau temuan yang Anda gunakan WAJIB disertai sitasi (Penulis, Tahun).\n"
                f"{rag_context}\n"
                "---\n"
            )
        else:
            rag_block = (
                "\n\n---\n"
                "BELOW IS THE ACTUAL CONTENT FROM RELEVANT PAPERS.\n"
                "Use this information as a SOURCE for your ANALYSIS and FINDINGS.\n"
                "NEVER copy sentences from this content — read, understand, then rewrite using YOUR OWN sentence structures and words.\n"
                "Every fact or finding you use MUST be cited with (Author, Year).\n"
                f"{rag_context}\n"
                "---\n"
            )

    # Only include paper list in part 1 to save tokens
    if part == 1:
        paper_list = build_paper_list(papers)
        prompt = (
            template.format(length_instruction=length_instruction, paper_list=paper_list)
            + rag_block
            + f'\n{theme_label}: "{theme}"\n\n'
            + section_info["instruction"]
            + "\n\nOutput ONLY the sections listed above. Nothing else."
        )
    else:
        brief_note = f"This journal is based on {len(papers)} papers about \"{theme}\". All papers are listed in Part 1."
        prompt = (
            f"{brief_note}{rag_block}\n\n"
            f"ALREADY WRITTEN (previous parts of the journal):\n\n{previous_content}\n\n"
            f"---\n\n"
            + section_info["instruction"]
            + "\n\nContinue from where the previous part left off. Do NOT repeat sections already written. Output ONLY the new sections."
        )

    return prompt
