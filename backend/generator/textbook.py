import re
import asyncio
from typing import Optional
from search.openalex import Paper
from providers.base import LLMProvider
from rag.store import store
from .agents import TokenTracker, _methodology_prompt, _lead_story_prompt


DEFAULT_SUBSECTIONS = {
    "id": ["Tujuan Pembelajaran", "Uraian Materi", "Rangkuman", "Latihan Soal"],
    "en": ["Learning Objectives", "Content", "Summary", "Exercises"],
}


def _template_subsections(template: Optional[dict], lang: str) -> list[str]:
    if not template:
        return DEFAULT_SUBSECTIONS[lang]
    subs = template.get("chapter_subsections", [])
    if not subs:
        return DEFAULT_SUBSECTIONS[lang]
    result = []
    for s in subs:
        heading = s.get(f"heading_{lang}", s.get("heading_id", ""))
        if heading:
            result.append(heading)
    return result or DEFAULT_SUBSECTIONS[lang]


CURRICULUM_SYSTEM_ID = (
    "Anda adalah ahli kurikulum dan desain pembelajaran yang merancang "
    "buku ajar sistematis. Tugas Anda adalah membuat daftar bab yang logis "
    "dan berurutan berdasarkan tema yang diberikan."
)

CURRICULUM_SYSTEM_EN = (
    "You are a curriculum and instructional design expert who creates "
    "systematic textbooks. Your role is to create a logical, sequential "
    "list of chapters based on the given theme."
)

TEXTBOOK_PROMPTS = {
    "methodology_analyst": {
        "id": (
            "Anda adalah Methodology Analyst yang ahli dalam metodologi penelitian. "
            "Tugas Anda adalah menentukan pendekatan penelitian, paradigma, dan metode analisis "
            "yang PALING TEPAT untuk sebuah tema buku ajar. "
            "Anda memahami berbagai paradigma dan metode analisis, serta mampu merekomendasikan "
            "pendekatan pedagogis yang sesuai untuk penyusunan buku ajar."
        ),
        "en": (
            "You are a Methodology Analyst specialized in research methodology. "
            "Your task is to determine the MOST APPROPRIATE research approach, paradigm, and analysis method "
            "for a textbook theme. "
            "You understand various paradigms and analysis methods, and can recommend "
            "a pedagogical approach suitable for textbook development."
        ),
    },
    "lead_researcher": {
        "id": (
            "Anda adalah Lead Researcher yang merencanakan isi buku ajar. "
            "Tugas Anda adalah membuat rencana detail untuk satu bab "
            "berdasarkan tema buku dan bab-bab sebelumnya."
        ),
        "en": (
            "You are a Lead Researcher planning textbook content. "
            "Your role is to create a detailed plan for one chapter "
            "based on the book theme and previous chapters."
        ),
    },
    "source_reviewer": {
        "id": (
            "Anda adalah Source Reviewer yang menganalisis literatur "
            "untuk buku ajar. Tugas Anda adalah mengekstrak konsep, "
            "teori, dan contoh relevan dari sumber untuk satu bab."
        ),
        "en": (
            "You are a Source Reviewer analyzing literature for a textbook. "
            "Your role is to extract relevant concepts, theories, and "
            "examples from sources for one chapter."
        ),
    },
    "lead_writer": {
        "id": (
            "Anda adalah penulis buku ajar yang berpengalaman. "
            "Tugas Anda adalah menulis satu bab buku ajar dengan "
            "gaya bahasa yang jelas, mudah dipahami, dan pedagogis. "
            "Gunakan penjelasan konseptual, contoh konkret, dan ilustrasi."
        ),
        "en": (
            "You are an experienced textbook author. "
            "Your role is to write one textbook chapter in a clear, "
            "easy-to-understand, pedagogical style. "
            "Use conceptual explanations, concrete examples, and illustrations."
        ),
    },
    "lead_story": {
        "id": (
            "Anda adalah Lead Storyteller yang ahli dalam menyajikan materi buku ajar "
            "secara naratif dan deskriptif. Tugas Anda adalah memperkaya konten bab "
            "dengan ilustrasi, analogi, contoh konkret, dan alur cerita yang menarik "
            "tanpa mengorbankan keakuratan ilmiah. Anda mengubah konsep abstrak "
            "menjadi narasi yang mudah dipahami dan diingat oleh pembaca."
        ),
        "en": (
            "You are a Lead Storyteller specialized in presenting textbook material "
            "in a narrative and descriptive way. Your role is to enrich chapter content "
            "with illustrations, analogies, concrete examples, and engaging story flow "
            "without sacrificing scientific accuracy. You transform abstract concepts "
            "into narratives that are easy to understand and remember."
        ),
    },
    "humanizer": {
        "id": (
            "Anda adalah Humanizer yang membuat teks buku ajar terdengar "
            "alami dan mengalir. Perbaiki kalimat yang kaku atau terlalu "
            "formal. Pertahankan konten, struktur, dan referensi."
        ),
        "en": (
            "You are a Humanizer who makes textbook text sound natural "
            "and flowing. Fix stiff or overly formal sentences. "
            "Preserve content, structure, and references."
        ),
    },
}


def _curriculum_prompt(language: str, theme: str, num_chapters: int) -> str:
    if language == "id":
        return f"""Buatlah daftar isi untuk buku ajar dengan tema: "{theme}"
Jumlah bab: {num_chapters}

Setiap bab harus:
1. Memiliki judul yang jelas dan relevan dengan tema
2. Berurutan secara logis (dari konsep dasar ke lanjutan)
3. Mencakup aspek-aspek penting dari tema secara komprehensif

Output dalam format:
Bab 1: [Judul Bab]
Bab 2: [Judul Bab]
...
Bab {num_chapters}: [Judul Bab]

Hanya output daftar bab, tanpa komentar tambahan."""
    return f"""Create a table of contents for a textbook with theme: "{theme}"
Number of chapters: {num_chapters}

Each chapter must:
1. Have a clear title relevant to the theme
2. Be logically sequenced (basic to advanced concepts)
3. Cover important aspects of the theme comprehensively

Output in format:
Chapter 1: [Chapter Title]
Chapter 2: [Chapter Title]
...
Chapter {num_chapters}: [Chapter Title]

Output ONLY the chapter list, no extra commentary."""


def _chapter_researcher_prompt(language: str, theme: str, chapter_num: int, chapter_title: str, previous_content: str) -> str:
    if language == "id":
        prev = f"\n\nBab-bab sebelumnya:\n{previous_content}\n\n---\n" if previous_content else ""
        return f"""Tema Buku Ajar: "{theme}"
Bab {chapter_num}: {chapter_title}{prev}

Tugas Anda sebagai Lead Researcher:
Buat rencana detail untuk Bab {chapter_num} ({chapter_title}).

Rencana harus mencakup:
1. Tujuan pembelajaran (3-5 poin)
2. Sub-topik utama yang perlu dicakup
3. Konsep kunci yang harus dijelaskan
4. Contoh atau ilustrasi yang relevan
5. Hubungan dengan bab sebelumnya

Keluarkan ONLY rencana bab, tanpa komentar tambahan."""
    prev = f"\n\nPrevious chapters:\n{previous_content}\n\n---\n" if previous_content else ""
    return f"""Textbook Theme: "{theme}"
Chapter {chapter_num}: {chapter_title}{prev}

Your task as Lead Researcher:
Create a detailed plan for Chapter {chapter_num} ({chapter_title}).

The plan must include:
1. Learning objectives (3-5 points)
2. Main sub-topics to cover
3. Key concepts to explain
4. Relevant examples or illustrations
5. Connection to previous chapters

Output ONLY the chapter plan, no extra commentary."""


def _chapter_reviewer_prompt(language: str, theme: str, chapter_num: int, chapter_title: str, research_plan: str, rag: str) -> str:
    if language == "id":
        return f"""Tema: "{theme}"
Bab {chapter_num}: {chapter_title}

Rencana Bab:
{research_plan}

Sumber Referensi:
{rag or "(tidak ada sumber spesifik)"}

Tugas Anda sebagai Source Reviewer:
Ekstrak konsep, teori, definisi, dan contoh dari sumber yang relevan
dengan rencana bab di atas.

Untuk setiap temuan:
- Sebutkan sumbernya
- Jelaskan relevansinya dengan bab ini
- Fokus pada materi yang bisa digunakan dalam buku ajar

Keluarkan ONLY hasil ekstraksi, terorganisir per topik."""
    return f"""Theme: "{theme}"
Chapter {chapter_num}: {chapter_title}

Chapter Plan:
{research_plan}

Source References:
{rag or "(no specific sources)"}

Your task as Source Reviewer:
Extract concepts, theories, definitions, and examples from sources
relevant to the chapter plan above.

For each finding:
- Mention the source
- Explain its relevance to this chapter
- Focus on material usable in a textbook

Output ONLY the extracted material, organized by topic."""


def _chapter_writer_prompt(language: str, theme: str, chapter_num: int, chapter_title: str, research_plan: str, findings: str, previous_content: str, paper_list: str, all_chapter_titles: str, subsections: Optional[list[str]] = None, has_data: bool = False, user_data: Optional[str] = None) -> str:
    from diagrams.prompts import diagram_instruction
    diag = diagram_instruction(has_data, language, user_data)
    no_ref = (
        "\n\nPENTING: HANYA gunakan sitasi inline (Penulis, Tahun). "
        "JANGAN pernah mencantumkan judul jurnal, volume, nomor, halaman, DOI, atau URL di badan bab. "
        "Referensi lengkap hanya di bagian Daftar Pustaka."
        if language == "id"
        else "\n\nIMPORTANT: Only use inline citations (Author, Year). "
        "NEVER include journal name, volume, issue, pages, DOI, or URLs in the chapter body. "
        "Full references belong only in the References section."
    )
    if language == "id":
        subs = subsections or DEFAULT_SUBSECTIONS["id"]
        prev = f"\n\nBAB SEBELUMNYA:\n{previous_content}\n\n---\n" if previous_content else ""
        sub_structure = "\n   ".join(f"### {s}" for s in subs)
        return f"""Tema Buku Ajar: "{theme}"
{all_chapter_titles}{prev}

Bab yang akan ditulis: Bab {chapter_num}: {chapter_title}

Rencana Bab:
{research_plan}

Materi dari Sumber:
{findings or "(tidak ada materi spesifik)"}

DAFTAR REFERENSI:
{paper_list}

ATURAN PENULISAN BUKU AJAR:
1. Gunakan heading ## untuk judul bab: ## Bab {chapter_num}: {chapter_title}
2. Gunakan heading ### untuk sub-bab
3. Gunakan heading #### untuk sub-topik dalam sub-bab
4. Setiap bab harus memiliki struktur:
   - ## Bab {chapter_num}: {chapter_title}
   - {sub_structure}
5. Target: sekitar 600-1000 kata per bab
6. Gunakan bahasa yang jelas, mudah dipahami, dan pedagogis
7. Sertakan contoh konkret dan ilustrasi konseptual
8. Gunakan tabel Markdown untuk perbandingan konsep.{diag}{no_ref}
9. Output ONLY konten bab, tanpa komentar tambahan"""
    subs = subsections or DEFAULT_SUBSECTIONS["en"]
    prev = f"\n\nPREVIOUS CHAPTER:\n{previous_content}\n\n---\n" if previous_content else ""
    sub_structure = "\n   ".join(f"### {s}" for s in subs)
    return f"""Textbook Theme: "{theme}"
{all_chapter_titles}{prev}

Chapter to write: Chapter {chapter_num}: {chapter_title}

Chapter Plan:
{research_plan}

Source Material:
{findings or "(no specific material)"}

REFERENCES:
{paper_list}

TEXTBOOK WRITING RULES:
1. Use ## heading for chapter title: ## Chapter {chapter_num}: {chapter_title}
2. Use ### heading for sub-sections
3. Use #### heading for sub-topics within sub-sections
4. Each chapter must have:
   - ## Chapter {chapter_num}: {chapter_title}
   - {sub_structure}
5. Target: approximately 600-1000 words per chapter
6. Use clear, easy-to-understand, pedagogical language
7. Include concrete examples and conceptual illustrations
8. Use Markdown tables for concept comparisons.{diag}{no_ref}
9. Output ONLY the chapter content, no extra commentary"""


def _chapter_humanizer_prompt(language: str, chapter_num: int, chapter_title: str, content: str) -> str:
    if language == "id":
        return f"""Bab {chapter_num}: {chapter_title}

KONTEN BAB:
{content}

---

Tugas Anda sebagai Humanizer:
Revisi konten bab di atas agar:
1. Terbaca alami seperti tulisan manusia (bukan AI)
2. Kalimat bervariasi (campur panjang-pendek)
3. Transisi antar paragraf halus
4. Awalan kalimat bervariasi
5. Pertahankan semua heading, struktur, dan makna
6. JANGAN ubah fakta atau konten signifikan

Output ONLY konten yang sudah dihumanisasi, tanpa komentar tambahan."""
    return f"""Chapter {chapter_num}: {chapter_title}

CHAPTER CONTENT:
{content}

---

Your task as Humanizer:
Revise the chapter content so that:
1. It reads naturally like human writing (not AI)
2. Sentences are varied (mix long and short)
3. Transitions between paragraphs are smooth
4. Sentence openings are varied
5. Preserve all headings, structure, and meaning
6. DO NOT change facts or significant content

Output ONLY the humanized content, no extra commentary."""


def _chapter_lead_story_prompt(language: str, chapter_num: int, chapter_title: str, content: str, methodology_context: str) -> str:
    if language == "id":
        return f"""Bab {chapter_num}: {chapter_title}

{methodology_context}

KONTEN BAB:
{content}

---

Tugas Anda sebagai Lead Storyteller:

Perkaya konten bab di atas dengan elemen naratif dan deskriptif.

Petunjuk:
1. **Ilustrasi konkret** — Tambahkan contoh nyata, analogi, atau perumpamaan yang relevan
2. **Alur naratif** — Pastikan sub-bab mengalir seperti cerita yang mudah diikuti
3. **Deskripsi hidup** — Ubah penjelasan abstrak menjadi gambaran yang konkret dan mudah dibayangkan
4. **Contoh aplikasi** — Tambahkan contoh bagaimana konsep diterapkan dalam situasi nyata
5. **Pertahankan** semua heading, struktur, dan keakuratan ilmiah
6. **JANGAN** mengubah fakta, data, atau definisi
7. **Output ONLY** konten yang sudah diperkaya, tanpa komentar tambahan"""
    return f"""Chapter {chapter_num}: {chapter_title}

{methodology_context}

CHAPTER CONTENT:
{content}

---

Your task as Lead Storyteller:

Enrich the chapter content above with narrative and descriptive elements.

Guidelines:
1. **Concrete illustrations** — Add real examples, analogies, or relevant comparisons
2. **Narrative flow** — Ensure sub-sections flow like a story that's easy to follow
3. **Vivid descriptions** — Turn abstract explanations into concrete, imaginable portrayals
4. **Application examples** — Add examples of how concepts are applied in real situations
5. **Preserve** all headings, structure, and scientific accuracy
6. **DO NOT** change facts, data, or definitions
7. **Output ONLY** the enriched content, no extra commentary"""


def _parse_chapters(text: str, num_chapters: int) -> list[str]:
    titles = []
    patterns = [
        re.compile(r"(?:Bab|Chapter)\s*\d+\s*[:\-–—]\s*(.+)", re.IGNORECASE),
        re.compile(r"^\d+[\.\)]\s*(.+)", re.IGNORECASE),
    ]
    for line in text.strip().split("\n"):
        line = line.strip()
        for p in patterns:
            m = p.match(line)
            if m:
                titles.append(m.group(1).strip().rstrip("."))
                break
    if len(titles) >= num_chapters:
        return titles[:num_chapters]
    if titles:
        return titles
    return [f"Chapter {i+1}" for i in range(num_chapters)]


async def generate_textbook(
    provider: LLMProvider,
    papers: list[Paper],
    theme: str,
    language: str,
    num_chapters: int,
    template: Optional[dict] = None,
    has_data: bool = False,
    user_data: Optional[str] = None,
    log_queue: Optional[asyncio.Queue] = None,
    previous_works_ctx: str = "",
) -> tuple[str, dict]:

    async def log(agent: str, msg: str, detail: str = ""):
        line = f"[{agent}] {msg}"
        print(line)
        if log_queue:
            await log_queue.put({
                "type": "log", "agent": agent,
                "message": msg, "detail": detail,
            })

    tracker = TokenTracker()
    lang = "id" if language == "id" else "en"
    subsections = _template_subsections(template, lang)
    if template and template.get("chapter_subsections"):
        await log("Textbook", f"Using template subsections: {subsections}")

    paper_list = "\n".join(
        f"[{i+1}] {p.authors[0] if p.authors else 'Unknown'} ({p.year}). {p.title}."
        for i, p in enumerate(papers)
    )

    # ---- Step 0: Methodology Analyst (runs once) ----
    await log("Methodology Analyst", "Menentukan metodologi penelitian...")
    methodology_sys = TEXTBOOK_PROMPTS["methodology_analyst"][lang]
    methodology_task = _methodology_prompt(lang, theme, paper_list, template)
    methodology_context = await tracker.run(provider, methodology_sys, methodology_task)
    await log("Methodology Analyst", f"Selesai ({len(methodology_context)} chars)")

    # Build template + methodology + previous-works context
    template_ctx = ""
    if template:
        from .agents import _format_template_constraints
        tc = _format_template_constraints(template, lang)
        if template.get("chapter_subsections"):
            subs_list = "\n".join(f"- ### {s}" for s in subsections)
            header = "STRUKTUR TEMPLATE SUB-BAB (setiap bab harus memiliki sub-bab berikut):" if lang == "id" else "TEMPLATE SUBSECTION STRUCTURE (each chapter must have these subsections):"
            template_ctx = f"\n\n{header}\n{subs_list}"
        template_ctx += tc + "\n\n"
    template_ctx += f"METODOLOGI PENELITIAN:\n{methodology_context}\n\n" if lang == "id" else f"RESEARCH METHODOLOGY:\n{methodology_context}\n\n"
    if previous_works_ctx:
        template_ctx += previous_works_ctx + "\n\n"

    # ---- Step 1: Curriculum Designer ----
    await log("Curriculum Designer", f"Mendesain kurikulum untuk {num_chapters} bab...")
    curriculum_sys = (template_ctx or "") + (CURRICULUM_SYSTEM_ID if language == "id" else CURRICULUM_SYSTEM_EN)
    curriculum_task = _curriculum_prompt(lang, theme, num_chapters)
    chapter_text = await tracker.run(provider, curriculum_sys, curriculum_task)
    chapters = _parse_chapters(chapter_text, num_chapters)
    await log("Curriculum Designer", f"{len(chapters)} bab dibuat")

    all_chapter_titles = "\n".join(f"Chapter {i+1}: {t}" for i, t in enumerate(chapters))
    all_content = ""
    prev_titles = ""

    for i, title in enumerate(chapters):
        chapter_num = i + 1
        await log("Pipeline", f"Bab {chapter_num}/{num_chapters}: {title}")

        # RAG context for this chapter
        rag = ""
        if papers:
            rag_results = store.search(f"{theme} {title}", top_k=5, min_score=0.05)
            if rag_results:
                rag = store.format_context(rag_results, papers)

        # 2. Lead Researcher (chapter plan)
        await log("Lead Researcher", "Membuat rencana bab...")
        researcher_sys = template_ctx + TEXTBOOK_PROMPTS["lead_researcher"][lang]
        task = _chapter_researcher_prompt(lang, theme, chapter_num, title, prev_titles)
        plan = await tracker.run(provider, researcher_sys, task)
        await log("Lead Researcher", f"Rencana selesai ({len(plan)} chars)")

        # 3. Source Reviewer
        await log("Source Reviewer", "Mengekstrak materi dari sumber...")
        reviewer_sys = template_ctx + TEXTBOOK_PROMPTS["source_reviewer"][lang]
        task = _chapter_reviewer_prompt(lang, theme, chapter_num, title, plan, rag)
        findings = await tracker.run(provider, reviewer_sys, task)
        await log("Source Reviewer", f"Ekstraksi selesai ({len(findings)} chars)")

        # 4. Lead Writer
        await log("Lead Writer", "Menulis bab...")
        writer_sys = template_ctx + TEXTBOOK_PROMPTS["lead_writer"][lang]
        task = _chapter_writer_prompt(lang, theme, chapter_num, title, plan, findings, prev_titles, paper_list, all_chapter_titles, subsections, has_data, user_data)
        chapter_content = await tracker.run(provider, writer_sys, task)
        await log("Lead Writer", f"Bab selesai ({len(chapter_content)} chars)")

        # 4b. Lead Storyteller (enrich descriptiveness)
        await log("Lead Storyteller", "Memperkaya dengan ilustrasi dan narasi...")
        story_sys = template_ctx + TEXTBOOK_PROMPTS["lead_story"][lang]
        story_task = _chapter_lead_story_prompt(lang, chapter_num, title, chapter_content, methodology_context)
        chapter_content = await tracker.run(provider, story_sys, story_task)
        await log("Lead Storyteller", "Pengayaan selesai")

        # 5. Humanizer
        await log("Humanizer", "Menghumanisasi bab...")
        humanizer_sys = TEXTBOOK_PROMPTS["humanizer"][lang]
        task = _chapter_humanizer_prompt(lang, chapter_num, title, chapter_content)
        chapter_content = await tracker.run(provider, humanizer_sys, task)
        await log("Humanizer", f"Selesai ({len(chapter_content)} chars)")

        await log("Pipeline", f"Bab {chapter_num} selesai")
        all_content += "\n\n" + chapter_content
        prev_titles += f"Bab {chapter_num}: {title}\n" if language == "id" else f"Chapter {chapter_num}: {title}\n"

    # Add Daftar Pustaka at the end
    id_heading = "## Daftar Pustaka"
    en_heading = "## References"
    heading = id_heading if language == "id" else en_heading
    all_content += f"\n\n{heading}\n\n" + "\n\n".join(
        f"[{i+1}] {p.authors[0] if p.authors else 'Unknown'} ({p.year}). {p.title}."
        for i, p in enumerate(papers)
    )

    return all_content, tracker.usage()
