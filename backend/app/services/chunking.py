from collections.abc import Iterable
from dataclasses import dataclass
import re

from app.services.pdf import PageText, normalize

SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class TextChunk:
    document_id: str
    page: int
    text: str

    @property
    def normalized_text(self) -> str:
        return normalize(self.text)


def chunk_pages(
    document_id: str, pages: Iterable[PageText], size: int, overlap: int
) -> list[TextChunk]:
    if size < 1 or not 0 <= overlap < size / 2:
        raise ValueError("Overlap must be non-negative and less than half the chunk size.")
    chunks = []
    for page in pages:
        start = 0
        while start < len(page.text):
            end = min(start + size, len(page.text))
            if end < len(page.text):
                # Prefer a word boundary in the second half of the window.
                for gap in SPACE.finditer(page.text, start + size // 2, end):
                    end_candidate = gap.end()
                    if end_candidate > start + overlap:
                        end = end_candidate
            text = page.text[start:end].strip()
            if text:
                chunks.append(TextChunk(document_id, page.number, text))
            if end == len(page.text):
                break
            start = end - overlap
    return chunks
