from typing import Optional

def diagram_instruction(has_data: bool, lang: str = "en", user_data: Optional[str] = None) -> str:
    user_block = ""
    if user_data:
        if lang == "id":
            user_block = f"\n\nDATA PENELITIAN (dari pengguna — gunakan untuk diagram dan analisis):\n{user_data}\n"
        else:
            user_block = f"\n\nUSER RESEARCH DATA (use this for diagrams and analysis):\n{user_data}\n"
    if has_data:
        if lang == "id":
            diag = (
                "\n\nDIAGRAM & TABEL:\n"
                "- Gunakan format blok ---DIAGRAM--- untuk menyertakan visualisasi data.\n"
                "- Format flowchart/concept_map: ---DIAGRAM---\\n{\"type\": \"flowchart\", \"title\": \"...\", \"nodes\": [...], \"edges\": [...]}\\n---END DIAGRAM---\n"
                "- Format bar/line/pie: ---DIAGRAM---\\n{\"type\": \"bar\", \"title\": \"...\", \"labels\": [...], \"values\": [...]}\\n---END DIAGRAM---\n"
                "- Hanya sertakan diagram jika benar-benar membantu pemahaman.\n"
                "- Gunakan data asli dari paper/sumber untuk diagram — JANGAN membuat data palsu."
            )
        else:
            diag = (
                "\n\nDIAGRAMS & TABLES:\n"
                "- Use ---DIAGRAM--- blocks to include data visualizations.\n"
                "- Flowchart/concept_map format: ---DIAGRAM---\\n{\"type\": \"flowchart\", \"title\": \"...\", \"nodes\": [...], \"edges\": [...]}\\n---END DIAGRAM---\n"
                "- Bar/line/pie format: ---DIAGRAM---\\n{\"type\": \"bar\", \"title\": \"...\", \"labels\": [...], \"values\": [...]}\\n---END DIAGRAM---\n"
                "- Only include diagrams when they truly improve clarity.\n"
                "- Use REAL data from papers/sources — do NOT fabricate data."
            )
    else:
        if lang == "id":
            diag = (
                "\n\nDIAGRAM (HANYA jika esensial):\n"
                "- Hanya flowchart/concept_map yang diizinkan — JANGAN buat diagram data numerik.\n"
                "- Format: ---DIAGRAM---\\n{\"type\": \"flowchart\", \"title\": \"...\", \"nodes\": [...], \"edges\": [...]}\\n---END DIAGRAM---\n"
                "- JANGAN pernah membuat data atau angka palsu."
            )
        else:
            diag = (
                "\n\nDIAGRAMS (ONLY if essential):\n"
                "- Only flowchart/concept_map types allowed — do NOT create data-driven charts.\n"
                "- Format: ---DIAGRAM---\\n{\"type\": \"flowchart\", \"title\": \"...\", \"nodes\": [...], \"edges\": [...]}\\n---END DIAGRAM---\n"
                "- NEVER fabricate data or numeric values."
            )
    return diag + user_block
