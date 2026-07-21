# app/utils.py
import uuid


def generate_product_id():
    x = uuid.uuid4()
    y = str(x)
    return y


def clean_text(text: str) -> str:
    """Strip and collapse whitespace; blank/whitespace-only input becomes ''."""
    return " ".join(text.split())


def chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split text into <=max_chars chunks, each overlapping the previous by `overlap` chars."""
    if overlap >= max_chars:
        raise ValueError("overlap must be smaller than max_chars")
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    step = max_chars - overlap
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + max_chars])
        if start + max_chars >= len(text):
            break
        start += step
    return chunks


# TODO: add validation
