from typing import Optional
from ..search.openalex import Paper
from ..providers.base import LLMProvider
from ..rag.store import store


SECTION_ORDER = [
    "title_abstract",
    "introduction",
    "literature_review",
    "method",
    "findings",
    "conclusion",
]

SECTION_META = {
    "id": {
        "title_abstract":  "## Judul\n## Abstrak",
        "introduction":    "## Pendahuluan",
        "literature_review": "## Tinjauan Pustaka",
        "method":          "## Metode Penelitian",
        "findings":        "## Temuan dan Pembahasan",
        "conclusion":      "## Penutup",
    },
    "en": {
        "title_abstract":  "## Title\n## Abstract",
        "introduction":    "## Introduction",
        "literature_review": "## Literature Review",
        "method":          "## Research Method",
        "findings":        "## Findings and Discussion",
        "conclusion":      "## Conclusion",
    },
}

RAG_QUERIES = {
    "introduction":      "{theme} introduction background context problem statement",
    "literature_review": "{theme} literature review previous research theoretical framework gap",
    "method":            "{theme} research method methodology approach design",
    "findings":          "{theme} findings results discussion analysis",
    "conclusion":        "{theme} conclusion implication limitation recommendation",
}

WORD_TARGET = {
    "short":    {"per_section": "250-400",    "total": "1500-2000"},
    "medium":   {"per_section": "700-1200",   "total": "4000-6000"},
    "long":     {"per_section": "1500-2500",  "total": "8000-12000"},
    "extended": {"per_section": "2500-4000",  "total": "15000-25000"},
}


SYSTEM_PROMPTS = {
    "lead_researcher": {
        "id": (
            "Anda adalah Lead Researcher yang ahli dalam metodologi penelitian kualitatif. "
            "Tugas Anda adalah merencanakan bagian-bagian jurnal akademik secara sistematis. "
            "Anda selalu berpikir kritis, mendalam, dan terstruktur."
        ),
        "en": (
            "You are a Lead Researcher specializing in qualitative research methodology. "
            "Your role is to systematically plan academic journal sections. "
            "You always think critically, deeply, and in a structured manner."
        ),
    },
    "source_reviewer": {
        "id": (
            "Anda adalah Source Reviewer yang ahli dalam menganalisis literatur akademik. "
            "Tugas Anda adalah menyintesis temuan-temuan dari paper yang relevan dengan rencana penelitian. "
            "Anda selalu mengekstrak fakta, data, dan argumen kunci — bukan menulis ulang konten."
        ),
        "en": (
            "You are a Source Reviewer skilled in analyzing academic literature. "
            "Your role is to synthesize findings from relevant papers according to the research plan. "
            "You always extract key facts, data, and arguments — not rewrite content."
        ),
    },
    "lead_writer": {
        "id": (
            "Anda adalah Lead Writer yang ahli dalam menulis jurnal akademik kualitatif. "
            "Tugas Anda adalah menulis bagian jurnal berdasarkan rencana penelitian dan temuan yang telah disintesis. "
            "Anda selalu menulis dengan kalimat orisinal, gaya akademik yang ketat, dan sitasi yang akurat."
        ),
        "en": (
            "You are a Lead Writer skilled in composing qualitative academic journals. "
            "Your role is to write journal sections based on the research plan and synthesized findings. "
            "You always write original sentences in strict academic style with accurate citations."
        ),
    },
    "peer_reviewer": {
        "id": (
            "Anda adalah Peer Reviewer yang sangat kritis, teliti, dan objektif. "
            "Tugas Anda adalah mengevaluasi naskah jurnal untuk memastikan: "
            "(1) kesesuaian dengan sumber referensi, "
            "(2) kesesuaian dengan tema dan arah penelitian, "
            "(3) orisinalitas tulisan (bukan hasil copy-paste), "
            "(4) kedalaman analisis, dan "
            "(5) akurasi sitasi. "
            "Anda memberikan kritik konstruktif yang spesifik dan actionable."
        ),
        "en": (
            "You are a highly critical, thorough, and objective Peer Reviewer. "
            "Your role is to evaluate journal manuscripts to ensure: "
            "(1) alignment with source references, "
            "(2) alignment with the research theme and direction, "
            "(3) originality of writing (not copy-pasted), "
            "(4) depth of analysis, and "
            "(5) citation accuracy. "
            "You provide constructive, specific, and actionable criticism."
        ),
    },
    "humanizer": {
        "id": (
            "Anda adalah Humanizer yang ahli dalam membuat teks akademik terdengar "
            "alami dan manusiawi. Tugas Anda adalah merevisi naskah jurnal agar terbaca "
            "seperti tulisan manusia, bukan AI. Anda mempertahankan makna, struktur, "
            "dan sitasi, tetapi memperbaiki pola kalimat yang kaku, repetitif, atau "
            "terlalu formal sehingga terdengar lebih alami dan mengalir."
        ),
        "en": (
            "You are a Humanizer specialized in making academic text sound natural "
            "and human-like. Your role is to revise journal manuscripts so they read "
            "like human writing, not AI-generated. You preserve meaning, structure, "
            "and citations, but fix stiff, repetitive, or overly formal sentence "
            "patterns to make the text flow naturally."
        ),
    },
}


# ---- Token tracking ----

class TokenTracker:
    def __init__(self):
        self.total_input = 0
        self.total_output = 0

    @staticmethod
    def estimate(text: str) -> int:
        return max(1, len(text) // 4)

    async def run(self, provider: LLMProvider, system: str, task: str) -> str:
        input_tokens = self.estimate(system) + self.estimate(task)
        result = await provider.generate(task, system_prompt=system)
        output_tokens = self.estimate(result)
        self.total_input += input_tokens
        self.total_output += output_tokens
        return result

    def usage(self) -> dict:
        return {"input_tokens": self.total_input, "output_tokens": self.total_output}


# ---- Helpers ----

def _build_paper_list(papers: list[Paper]) -> str:
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


def _rag_context(papers: list[Paper], query: str) -> str:
    rag_results = store.search(query, top_k=5, min_score=0.05)
    if not rag_results:
        return ""
    return store.format_context(rag_results, papers)


def _get_paper_list(papers: list[Paper]) -> str:
    return _build_paper_list(papers)


# ---- Prompt builders ----

def _researcher_prompt(language: str, section_key: str, theme: str, section_heading: str, rag: str, previous: str) -> str:
    if language == "id":
        return f"""Tema Penelitian: "{theme}"

Bagian yang akan ditulis: {section_heading}

Konteks dari paper yang relevan:
{rag or "(tidak ada konten spesifik)"}

{('Bagian yang sudah ditulis sebelumnya:\\n\\n' + previous + '\\n\\n---\\n\\n') if previous else ''}

Tugas Anda sebagai Lead Researcher:
Buatlah rencana penelitian yang DETAIL untuk bagian {section_heading}.

Rencana harus mencakup:
1. Poin-poin utama yang perlu dicakup
2. Argumen atau analisis spesifik yang perlu dikembangkan
3. Paper mana yang relevan untuk setiap poin
4. Struktur/alur penulisan yang logis

Keluarkan ONLY rencana penelitian, tanpa komentar tambahan."""
    return f"""Research Theme: "{theme}"

Section to write: {section_heading}

Relevant paper context:
{rag or "(no specific content available)"}

{('Previously written sections:\\n\\n' + previous + '\\n\\n---\\n\\n') if previous else ''}

Your task as Lead Researcher:
Create a DETAILED research plan for the {section_heading} section.

The plan must include:
1. Key points to cover
2. Specific arguments or analyses to develop
3. Which papers are relevant for each point
4. Logical structure/flow

Output ONLY the research plan, no extra commentary."""


def _reviewer_prompt(language: str, section_key: str, theme: str, section_heading: str, research_plan: str, rag: str) -> str:
    if language == "id":
        return f"""Tema Penelitian: "{theme}"
Bagian: {section_heading}

Rencana Penelitian (dari Lead Researcher):
{research_plan}

Konteks dari paper yang relevan:
{rag or "(tidak ada konten spesifik)"}

Tugas Anda sebagai Source Reviewer:
Analisis konteks paper di atas dan ekstrak temuan-temuan kunci yang relevan dengan rencana penelitian.

Untuk setiap temuan:
- Sebutkan paper sumber dengan sitasi (Penulis, Tahun)
- Jelaskan bagaimana temuan ini mendukung rencana penelitian
- Fokus pada fakta konkret dan data, BUKAN menulis ulang untuk bagian jurnal

Keluarkan ONLY hasil sintesis temuan, diorganisir berdasarkan tema."""
    return f"""Research Theme: "{theme}"
Section: {section_heading}

Research Plan (from Lead Researcher):
{research_plan}

Relevant paper context:
{rag or "(no specific content available)"}

Your task as Source Reviewer:
Analyze the paper context above and extract key findings relevant to the research plan.

For each finding:
- Cite the source paper with (Author, Year)
- Explain how this finding supports the research plan
- Focus on concrete facts and data, NOT on rewriting journal content

Output ONLY the synthesized findings, organized by theme."""


def _writer_prompt(language: str, section_key: str, theme: str, section_heading: str, research_plan: str, findings: str, word_target: str, previous: str, paper_list: str) -> str:
    if language == "id":
        base = f"""Tema Penelitian: "{theme}"
Bagian yang akan ditulis: {section_heading}

Rencana Penelitian (dari Lead Researcher):
{research_plan}

Temuan yang Disintesis (dari Source Reviewer):
{findings or "(tidak ada temuan spesifik)"}

{('Bagian yang sudah ditulis sebelumnya:\\n\\n' + previous + '\\n\\n---\\n\\n') if previous else ''}

DAFTAR REFERENSI (semua paper yang tersedia):
{paper_list}

ATURAN PENULISAN:
1. Gunakan heading ## untuk setiap sub-bagian — JANGAN gunakan heading bernomor (#, ###, ####)
2. Setiap klaim WAJIB disertai sitasi inline format APA: (Penulis, Tahun)
3. Tulis kalimat ORISINAL — jangan menyalin dari konteks atau abstrak
4. Target panjang: sekitar {word_target} kata untuk bagian ini
5. Output ONLY konten bagian dengan heading ##, tanpa komentar tambahan"""
    else:
        base = f"""Research Theme: "{theme}"
Section to write: {section_heading}

Research Plan (from Lead Researcher):
{research_plan}

Synthesized Findings (from Source Reviewer):
{findings or "(no specific findings)"}

{('Previously written sections:\\n\\n' + previous + '\\n\\n---\\n\\n') if previous else ''}

PAPER LIST (all available papers):
{paper_list}

WRITING RULES:
1. Use ## headings for each sub-section — do NOT use numbered headings
2. Every claim MUST have an inline APA citation: (Author, Year)
3. Write ORIGINAL sentences — do not copy from context or abstracts
4. Target length: approximately {word_target} words for this section
5. Output ONLY the section content with ## headings, no extra commentary"""

    if section_key == "title_abstract":
        base += (
            "\n\nTulis judul yang menarik dan abstrak yang merangkum keseluruhan jurnal."
            if language == "id"
            else "\n\nWrite an engaging title and an abstract that summarizes the entire journal."
        )
    return base


def _peer_review_prompt(language: str, theme: str, section_heading: str, research_plan: str, findings: str, section_content: str) -> str:
    if language == "id":
        return f"""Tema Penelitian: "{theme}"
Bagian yang Dievaluasi: {section_heading}

Rencana Penelitian:
{research_plan}

Temuan dari Sumber:
{findings or "(tidak ada temuan spesifik)"}

Naskah yang Ditulis:
{section_content}

---

Tugas Anda sebagai Peer Reviewer:

Evaluasi naskah di atas secara kritis berdasarkan 6 aspek berikut:

1. **Kesesuaian dengan Sumber** — Apakah analisis dan klaim dalam naskah sesuai dengan temuan dari paper? Beri contoh jika menyimpang.
2. **Kesesuaian dengan Tema** — Apakah fokus naskah tetap pada tema penelitian? Apakah tidak melenceng?
3. **Orisinalitas** — Apakah kalimat-kalimatnya merupakan hasil pemikiran dan parafrase asli? Apakah ada kalimat yang mencurigakan sebagai salinan dari sumber?
4. **Akurasi Sitasi** — Apakah setiap klaim didukung sitasi (Penulis, Tahun)? Apakah ada klaim tanpa sitasi?
5. **Struktur dan Alur** — Apakah naskah terorganisir dengan baik dan mudah diikuti?
6. **Kedalaman Analisis** — Apakah analisisnya cukup mendalam? Apakah ada bagian yang dangkal atau perlu dikembangkan lebih lanjut?

Format evaluasi:
- Untuk setiap aspek, tulis **PASS** atau **REVISE**.
- Jika REVISE, berikan alasan spesifik dan saran perbaikan yang konkret.
- Kutip baris atau kalimat spesifik dari naskah sebagai contoh jika perlu.

Akhiri review dengan:
**KEPUTUSAN AKHIR: [APPROVED / REVISION NEEDED]**
"""
    return f"""Research Theme: "{theme}"
Section Evaluated: {section_heading}

Research Plan:
{research_plan}

Source Findings:
{findings or "(no specific findings)"}

Written Section:
{section_content}

---

Your task as Peer Reviewer:

Critically evaluate the section above based on 6 aspects:

1. **Source Alignment** — Does the analysis and claims match the source findings? Provide examples if misaligned.
2. **Theme Alignment** — Does the section stay focused on the research theme? Does it avoid going off-topic?
3. **Originality** — Are the sentences original thoughts and paraphrases? Are there any sentences that appear to be copied from sources?
4. **Citation Accuracy** — Is every claim supported by a citation (Author, Year)? Are there claims without citations?
5. **Structure & Flow** — Is the section well-organized and easy to follow?
6. **Depth of Analysis** — Is the analysis deep enough? Are there areas that need more development?

Format:
- For each aspect, write **PASS** or **REVISE**.
- If REVISE, give specific reasons and concrete suggestions.
- Quote specific lines from the section as examples if needed.

End with:
**FINAL DECISION: [APPROVED / REVISION NEEDED]**
"""


def _revision_prompt(language: str, theme: str, section_heading: str, research_plan: str, findings: str, section_content: str, peer_review: str, paper_list: str, previous: str) -> str:
    if language == "id":
        return f"""Tema Penelitian: "{theme}"
Bagian: {section_heading}

Rencana Penelitian:
{research_plan}

Temuan dari Sumber:
{findings or "(tidak ada temuan spesifik)"}

{('Bagian yang sudah ditulis sebelumnya:\\n\\n' + previous + '\\n\\n---\\n\\n') if previous else ''}

DAFTAR REFERENSI:
{paper_list}

---

NASKAH SEBELUM REVISI:
{section_content}

---

UMBAN BALIK PEER REVIEWER:
{peer_review}

---

Tugas Anda sebagai Lead Writer:

Revisi naskah di ATAS berdasarkan umpan balik Peer Reviewer di ATAS.

Petunjuk:
1. Perbaiki SEMUA masalah yang diidentifikasi reviewer
2. Pertahankan bagian yang sudah dinilai PASS
3. Pastikan setiap klaim tetap punya sitasi (Penulis, Tahun)
4. Tulis dengan kalimat ORISINAL — jangan copy dari sumber
5. Gunakan heading ##

Output ONLY naskah yang sudah direvisi dengan heading ##, tanpa komentar tambahan."""
    return f"""Research Theme: "{theme}"
Section: {section_heading}

Research Plan:
{research_plan}

Source Findings:
{findings or "(no specific findings)"}

{('Previously written sections:\\n\\n' + previous + '\\n\\n---\\n\\n') if previous else ''}

PAPER LIST:
{paper_list}

---

SECTION BEFORE REVISION:
{section_content}

---

PEER REVIEWER FEEDBACK:
{peer_review}

---

Your task as Lead Writer:

Revise the section ABOVE based on the Peer Reviewer feedback ABOVE.

Guidelines:
1. Fix ALL issues identified by the reviewer
2. Keep parts that were rated PASS
3. Ensure every claim still has a citation (Author, Year)
4. Write ORIGINAL sentences — do not copy from sources
5. Use ## headings

Output ONLY the revised section with ## headings, no extra commentary."""


def _researcher_revision_prompt(language: str, theme: str, section_heading: str, old_plan: str, findings: str, section_content: str, peer_review: str, previous: str) -> str:
    if language == "id":
        return f"""Tema Penelitian: "{theme}"
Bagian: {section_heading}

Rencana Penelitian SEBELUMNYA:
{old_plan}

Temuan dari Sumber:
{findings or "(tidak ada temuan spesifik)"}

Naskah yang Sudah Ditulis:
{section_content}

UMBAN BALIK PEER REVIEWER:
{peer_review}

{('Bagian yang sudah ditulis sebelumnya:\\n\\n' + previous + '\\n\\n---\\n\\n') if previous else ''}

Tugas Anda sebagai Lead Researcher:

Tinjau rencana penelitian SEBELUMNYA dan umpan balik Peer Reviewer.
Perbaiki rencana penelitian agar lebih sesuai dengan:
1. Kritik dan saran dari Peer Reviewer
2. Temuan dari sumber yang relevan
3. Arah dan tujuan penelitian

Keluarkan ONLY rencana penelitian yang sudah direvisi, tanpa komentar tambahan."""
    return f"""Research Theme: "{theme}"
Section: {section_heading}

PREVIOUS Research Plan:
{old_plan}

Source Findings:
{findings or "(no specific findings)"}

Written Section:
{section_content}

PEER REVIEWER FEEDBACK:
{peer_review}

{('Previously written sections:\\n\\n' + previous + '\\n\\n---\\n\\n') if previous else ''}

Your task as Lead Researcher:

Review the PREVIOUS research plan and the Peer Reviewer feedback.
Revise the research plan to better align with:
1. The Peer Reviewer's criticism and suggestions
2. Relevant source findings
3. The research direction and goals

Output ONLY the revised research plan, no extra commentary."""


def _humanizer_prompt(language: str, theme: str, section_heading: str, section_content: str) -> str:
    if language == "id":
        return f"""Tema Penelitian: "{theme}"
Bagian: {section_heading}

NASKAH YANG AKAN DIHUMANISASI:
{section_content}

---

Tugas Anda sebagai Humanizer:

Revisi naskah di atas agar terdengar seperti tulisan manusia, bukan AI-generasi.

Petunjuk:
1. **Variasi kalimat** — Campur kalimat panjang dan pendek. Jangan semua kalimat punya struktur yang sama.
2. **Hilangkan pola repetitif** — Cari frasa yang diulang-ulang dan ganti dengan variasi.
3. **Transisi alami** — Pastikan alur antar paragraf mengalir alami.
4. **Awalan bervariasi** — Jangan mulai setiap kalimat dengan "Penelitian ini..." atau "Hasil menunjukkan...".
5. **Pertahankan** semua heading ##, sitasi (Penulis, Tahun), dan makna asli.
6. **JANGAN** mengubah fakta, data, atau argumen.
7. **JANGAN** menambah atau menghapus konten signifikan — hanya perbaiki gaya bahasa.

Output ONLY naskah yang sudah dihumanisasi dengan heading ##, tanpa komentar tambahan."""
    return f"""Research Theme: "{theme}"
Section: {section_heading}

TEXT TO HUMANIZE:
{section_content}

---

Your task as Humanizer:

Revise the text above to sound like human writing, not AI-generated.

Guidelines:
1. **Sentence variety** — Mix long and short sentences. Avoid identical structures.
2. **Remove repetitive patterns** — Find repeated phrases and vary them.
3. **Natural transitions** — Ensure smooth flow between paragraphs.
4. **Vary openings** — Don't start every sentence with "This study..." or "The results...".
5. **Preserve** all ## headings, citations (Author, Year), and original meaning.
6. **DO NOT** change facts, data, or arguments.
7. **DO NOT** add or remove significant content — only improve the writing style.

Output ONLY the humanized text with ## headings, no extra commentary."""


# ---- Orchestration ----

async def generate_multi_agent(
    provider: LLMProvider,
    papers: list[Paper],
    theme: str,
    language: str,
    target_length: str,
) -> tuple[str, dict]:
    tracker = TokenTracker()
    lang = "id" if language == "id" else "en"
    headings = SECTION_META[lang]
    word_info = WORD_TARGET.get(target_length, WORD_TARGET["medium"])
    word_target = word_info["per_section"]

    all_content = ""
    paper_list = _get_paper_list(papers)

    for section_key in SECTION_ORDER:
        heading = headings[section_key]
        print(f"[Agent] Processing section: {section_key} ({heading})")

        query_template = RAG_QUERIES.get(section_key)
        rag = _rag_context(papers, query_template.format(theme=theme)) if query_template else ""

        # 1. Lead Researcher
        researcher_sys = SYSTEM_PROMPTS["lead_researcher"][lang]
        task = _researcher_prompt(lang, section_key, theme, heading, rag, all_content)
        research_plan = await tracker.run(provider, researcher_sys, task)
        print(f"[Agent] Lead Researcher done: {len(research_plan)} chars")

        # 2. Source Reviewer
        reviewer_sys = SYSTEM_PROMPTS["source_reviewer"][lang]
        task = _reviewer_prompt(lang, section_key, theme, heading, research_plan, rag)
        findings = await tracker.run(provider, reviewer_sys, task)
        print(f"[Agent] Source Reviewer done: {len(findings)} chars")

        # 3. Lead Writer (first draft)
        writer_sys = SYSTEM_PROMPTS["lead_writer"][lang]
        task = _writer_prompt(lang, section_key, theme, heading, research_plan, findings, word_target, all_content, paper_list)
        section_content = await tracker.run(provider, writer_sys, task)
        print(f"[Agent] Lead Writer (draft) done: {len(section_content)} chars")

        # 4. Peer Reviewer
        peer_sys = SYSTEM_PROMPTS["peer_reviewer"][lang]
        task = _peer_review_prompt(lang, theme, heading, research_plan, findings, section_content)
        peer_review = await tracker.run(provider, peer_sys, task)
        print(f"[Agent] Peer Reviewer done: {len(peer_review)} chars")

        # 5. Lead Researcher (revision)
        research_revision_task = _researcher_revision_prompt(lang, theme, heading, research_plan, findings, section_content, peer_review, all_content)
        research_plan = await tracker.run(provider, researcher_sys, research_revision_task)
        print(f"[Agent] Lead Researcher (revised) done: {len(research_plan)} chars")

        # 6. Lead Writer (revision)
        task = _revision_prompt(lang, theme, heading, research_plan, findings, section_content, peer_review, paper_list, all_content)
        section_content = await tracker.run(provider, writer_sys, task)
        print(f"[Agent] Lead Writer (revised) done: {len(section_content)} chars")

        # 7. Humanizer
        humanizer_sys = SYSTEM_PROMPTS["humanizer"][lang]
        task = _humanizer_prompt(lang, theme, heading, section_content)
        section_content = await tracker.run(provider, humanizer_sys, task)
        print(f"[Agent] Humanizer done: {len(section_content)} chars")

        all_content += "\n\n" + section_content

    return all_content, tracker.usage()
