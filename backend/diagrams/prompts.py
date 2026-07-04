import re
from typing import Optional


def _has_numbers(text: str) -> bool:
    return bool(re.search(r"\d+[.,]\s*\d+", text))


def diagram_instruction(
    has_data: bool,
    lang: str = "en",
    user_data: Optional[str] = None,
    content: str = "",
) -> str:
    user_block = ""
    if user_data:
        if lang == "id":
            user_block = f"\n\nDATA PENELITIAN (dari pengguna — gunakan untuk diagram dan analisis):\n{user_data}\n"
        else:
            user_block = f"\n\nUSER RESEARCH DATA (use this for diagrams and analysis):\n{user_data}\n"

    has_numbers = has_data or _has_numbers(content)

    if has_data or has_numbers:
        if lang == "id":
            diag = (
                "\n\nDIAGRAM & TABEL:\n"
                "- Gunakan format blok ---DIAGRAM--- untuk menyertakan visualisasi data.\n"
                "- Format flowchart/concept_map: ---DIAGRAM---\\n{\"type\": \"flowchart\", \"title\": \"...\", \"nodes\": [...], \"edges\": [...]}\\n---END DIAGRAM---\n"
                "- Format bar/line/pie: ---DIAGRAM---\\n{\"type\": \"bar\", \"title\": \"...\", \"labels\": [...], \"values\": [...]}\\n---END DIAGRAM---\n"
                "- Hanya sertakan diagram jika benar-benar membantu pemahaman.\n"
                "- Gunakan DATA ASLI dari naskah/literatur untuk diagram — JANGAN membuat data palsu.\n"
                "- PERINGATAN: Jangan gunakan backslash \\ di dalam string JSON! Misalnya jangan tulis \\R^2 atau \\beta — tulis saja R^2 atau beta."
            )
        else:
            diag = (
                "\n\nDIAGRAMS & TABLES:\n"
                "- Use ---DIAGRAM--- blocks to include data visualizations.\n"
                "- Flowchart/concept_map format: ---DIAGRAM---\\n{\"type\": \"flowchart\", \"title\": \"...\", \"nodes\": [...], \"edges\": [...]}\\n---END DIAGRAM---\n"
                "- Bar/line/pie format: ---DIAGRAM---\\n{\"type\": \"bar\", \"title\": \"...\", \"labels\": [...], \"values\": [...]}\\n---END DIAGRAM---\n"
                "- Only include diagrams when they truly improve clarity.\n"
                "- Use REAL data from the text/sources — do NOT fabricate data.\n"
                "- WARNING: Never use backslash \\ inside JSON strings! For example, write \"R^2\" instead of \"\\R^2\", and \"beta\" instead of \"\\beta\"."
            )
    else:
        if lang == "id":
            diag = (
                "\n\nDIAGRAM (HANYA jika esensial):\n"
                "- Hanya flowchart/concept_map yang diizinkan.\n"
                "- Format: ---DIAGRAM---\\n{\"type\": \"flowchart\", \"title\": \"...\", \"nodes\": [...], \"edges\": [...]}\\n---END DIAGRAM---\n"
                "- JANGAN pernah membuat data atau angka palsu."
            )
        else:
            diag = (
                "\n\nDIAGRAMS (ONLY if essential):\n"
                "- Only flowchart/concept_map types allowed.\n"
                "- Format: ---DIAGRAM---\\n{\"type\": \"flowchart\", \"title\": \"...\", \"nodes\": [...], \"edges\": [...]}\\n---END DIAGRAM---\n"
                "- NEVER fabricate data or numeric values."
            )
    return diag + user_block

