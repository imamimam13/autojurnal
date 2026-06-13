import re


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 50) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text.strip())
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        para_len = len(para)
        if para_len > chunk_size:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            for i in range(0, para_len, chunk_size - overlap):
                chunks.append(para[i : i + chunk_size])
        elif current_len + para_len > chunk_size:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = para_len
        else:
            current.append(para)
            current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks
