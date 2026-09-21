import unittest
import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from typing import Optional
from generator.memory import (
    RollingMemory,
    compact_previous_content,
    truncate_context_budget,
    is_context_overflow_error,
    compress_prompt_for_retry,
)
from providers.base import LLMProvider
from search.openalex import Paper
from generator.journal import build_part_prompt


class MockProvider(LLMProvider):
    def __init__(self, name: str = "mock", fail_with_context_error: bool = False):
        self._name = name
        self.fail_with_context_error = fail_with_context_error
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return f"Mock Provider ({self._name})"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        self.call_count += 1
        if self.fail_with_context_error and self.call_count == 1:
            raise Exception("400 Bad Request: context_length_exceeded: maximum context length is 4096 tokens")
        return f"Generated response for call {self.call_count} (prompt length: {len(prompt)})"


class StandaloneTokenTracker:
    def __init__(self):
        self.total_input = 0
        self.total_output = 0

    @staticmethod
    def estimate(text: str) -> int:
        return max(1, len(text) // 4)

    async def run(self, provider: LLMProvider, system: str, task: str, lang: str = "id") -> str:
        input_tokens = self.estimate(system) + self.estimate(task)
        try:
            result = await provider.generate(task, system_prompt=system)
        except Exception as e:
            if is_context_overflow_error(e):
                compressed_sys, compressed_task = compress_prompt_for_retry(system, task, lang=lang)
                result = await provider.generate(compressed_task, system_prompt=compressed_sys)
            else:
                raise
        output_tokens = self.estimate(result)
        self.total_input += input_tokens
        self.total_output += output_tokens
        return result


class TestMemoryCarryover(unittest.TestCase):

    def test_rolling_memory_basic(self):
        mem = RollingMemory(max_recent=2, max_chars=1000, lang="id")
        mem.add("## Pendahuluan", "- AI meningkatkan efisiensi\n- Masalah akurasi diagnostik")
        mem.add("## Tinjauan Pustaka", "- Teori difusi inovasi\n- Penelitian terdahulu")

        summary = mem.get_summary()
        self.assertIn("Pendahuluan", summary)
        self.assertIn("Tinjauan Pustaka", summary)
        self.assertEqual(len(mem), 2)

    def test_rolling_memory_carryover_compaction(self):
        mem = RollingMemory(max_recent=2, max_chars=800, lang="id")
        mem.add("## Bagian 1", "- Poin 1A\n- Poin 1B")
        mem.add("## Bagian 2", "- Poin 2A\n- Poin 2B")
        mem.add("## Bagian 3", "- Poin 3A\n- Poin 3B")
        mem.add("## Bagian 4", "- Poin 4A\n- Poin 4B")

        summary = mem.get_summary()
        self.assertIn("Ringkasan Bagian Terdahulu (Carry-Over)", summary)
        self.assertIn("Bagian 1", summary)
        self.assertIn("Bagian 2", summary)
        self.assertIn("### Bagian 3", summary)
        self.assertIn("### Bagian 4", summary)

    def test_compact_previous_content(self):
        short_content = "## Pendahuluan\nIni pendahuluan singkat."
        self.assertEqual(compact_previous_content(short_content, max_chars=5000), short_content)

        large_content = "## Judul\nJudul Jurnal\n\n## Pendahuluan\n" + ("A" * 10000) + "\n\n## Metode\n" + ("B" * 5000)
        compacted = compact_previous_content(large_content, max_chars=4000, lang="id")
        self.assertLess(len(compacted), len(large_content))
        self.assertIn("Struktur yang sudah ditulis sebelumnya", compacted)
        self.assertIn("## Pendahuluan", compacted)
        self.assertIn("## Metode", compacted)

    def test_truncate_context_budget(self):
        text = "X" * 10000
        truncated = truncate_context_budget(text, max_chars=2000)
        self.assertLessEqual(len(truncated), 2100)
        self.assertIn("konten dipotong", truncated)

    def test_context_overflow_detection(self):
        self.assertTrue(is_context_overflow_error(Exception("400 Bad Request: context_length_exceeded")))
        self.assertTrue(is_context_overflow_error(Exception("CUDA out of memory in llama_context")))
        self.assertTrue(is_context_overflow_error(Exception("maximum context length is 8192 tokens")))
        self.assertTrue(is_context_overflow_error(Exception("Prompt is too long: 12000 tokens exceed model max of 8192")))
        self.assertFalse(is_context_overflow_error(Exception("Connection refused to 127.0.0.1:11434")))

    def test_compress_prompt_for_retry(self):
        sys_prompt = "Instruksi sistem " * 200
        user_prompt = "Tugas naskah " * 1000
        comp_sys, comp_task = compress_prompt_for_retry(sys_prompt, user_prompt, lang="id")
        self.assertLess(len(comp_sys), len(sys_prompt))
        self.assertLess(len(comp_task), len(user_prompt))

    def test_tokentracker_self_healing_retry(self):
        async def _run():
            provider = MockProvider("mock_overflow", fail_with_context_error=True)
            tracker = StandaloneTokenTracker()
            system = "Sistem instruksi " * 50
            task = "Tugas prompt panjang " * 500

            result = await tracker.run(provider, system, task, lang="id")
            self.assertEqual(provider.call_count, 2)
            self.assertIn("Generated response", result)

        asyncio.run(_run())

    def test_build_part_prompt_with_carryover(self):
        paper = Paper(
            title="AI Study",
            abstract="Abstract of AI Study",
            authors=["Smith"],
            year=2024,
            doi="10.1234/test",
            openalex_url=None,
            url=None,
            pdf_url=None,
            source="Nature",
            cited_by_count=10,
        )
        prev_text = "## Judul\nStudi AI\n\n## Pendahuluan\n" + ("Teks intro panjang " * 500)
        prompt = build_part_prompt(
            papers=[paper],
            language="id",
            theme="AI dalam Pendidikan",
            target_length="medium",
            part=2,
            num_parts=2,
            previous_content=prev_text,
        )
        self.assertIn("ALREADY WRITTEN", prompt)
        self.assertLess(len(prompt), len(prev_text) + 5000)

    def test_works_store_save_get_delete(self):
        from store.works import WorkRecord, WorksStore
        import tempfile
        store = WorksStore()
        work = WorkRecord(
            work_id="test-work-12345",
            theme="Corporate Social Responsibility",
            content="Full journal text about CSR and governance.",
            language="id",
            mode="journal",
            provider="test-llm",
            paper_titles=["CSR Paper 1"],
        )
        store.save_work(work)
        retrieved = store.get_work("test-work-12345")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["theme"], "Corporate Social Responsibility")
        self.assertIn("Full journal text", retrieved["content"])

        deleted = store.delete_work("test-work-12345")
        self.assertTrue(deleted)
        self.assertIsNone(store.get_work("test-work-12345"))

    def test_alphabetical_reference_sorting(self):
        from main import format_reference, replace_references
        papers = [
            Paper(title="Zebra Study", abstract="", authors=["Reza Akbar"], year=2024, doi=None, openalex_url=None, url=None, pdf_url=None, source="Journal of AI", cited_by_count=10),
            Paper(title="Alpha Study", abstract="", authors=["Ardiansyah"], year=2023, doi=None, openalex_url=None, url=None, pdf_url=None, source="Journal of Data", cited_by_count=5),
            Paper(title="Beta Study", abstract="", authors=["Francesca Collevecchio", "G. Gionfriddo"], year=2022, doi=None, openalex_url=None, url=None, pdf_url=None, source="Journal of Math", cited_by_count=15),
            Paper(title="Gamma Study", abstract="", authors=["Tachia Chin", "Author B", "Author C"], year=2021, doi=None, openalex_url=None, url=None, pdf_url=None, source="Journal of Science", cited_by_count=20),
            Paper(title="Delta Study", abstract="", authors=["Welsi Damayanti"], year=2020, doi=None, openalex_url=None, url=None, pdf_url=None, source="Journal of Physics", cited_by_count=8),
        ]
        journal_text = "# Title\n\nSome body content.\n\n## Daftar Pustaka\n\nOld content"
        res = replace_references(journal_text, papers, language="id")

        # Verify references are formatted in APA style
        self.assertIn("Akbar, R. (2024). Zebra Study.", res)
        self.assertIn("Ardiansyah (2023). Alpha Study.", res)
        self.assertIn("Collevecchio, F. & Gionfriddo, G. (2022). Beta Study.", res)
        self.assertIn("Chin, T. et al. (2021). Gamma Study.", res)
        self.assertIn("Damayanti, W. (2020). Delta Study.", res)

        # Extract lines after ## Daftar Pustaka
        ref_section = res.split("## Daftar Pustaka\n\n")[1].strip().split("\n\n")
        ref_first_letters = [r[0].upper() for r in ref_section]
        self.assertEqual(ref_first_letters, sorted(ref_first_letters))
        self.assertEqual(ref_section, sorted(ref_section, key=lambda s: s.lower()))


if __name__ == "__main__":
    unittest.main()
