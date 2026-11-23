from dataclasses import dataclass
import re

import pymupdf

from app.core.errors import KnowledgeError

PDF_HEADER = re.compile(rb"^%PDF-[12]\.\d(?:\r|\n)")
MAX_TEXT_LENGTH = 2_000_000


@dataclass(frozen=True)
class PageText:
    number: int
    text: str


def normalize(text: str) -> str:
    return " ".join(text.split())


def extract_pages(content: bytes, max_pages: int) -> list[PageText]:
    if not PDF_HEADER.match(content):
        raise KnowledgeError(415, "invalid_pdf_signature", "Select a file with a valid PDF signature.")
    try:
        with pymupdf.open(stream=content, filetype="pdf") as pdf:
            if pdf.is_repaired or not pdf.page_count:
                raise KnowledgeError(422, "corrupt_pdf", "The PDF is corrupted or has no pages.")
            if pdf.needs_pass:
                raise KnowledgeError(422, "encrypted_pdf", "Remove password protection before uploading.")
            if pdf.page_count > max_pages:
                raise KnowledgeError(422, "page_limit", f"The PDF exceeds the {max_pages}-page limit.")
            pages = []
            text_length = 0
            for page in pdf:
                text = page.get_text(sort=True)
                text_length += len(text)
                if text_length > MAX_TEXT_LENGTH:
                    raise KnowledgeError(422, "text_limit", "The PDF contains too much text. Split it into smaller PDFs.")
                pages.append(PageText(page.number + 1, text))
    except (RuntimeError, ValueError) as exc:
        raise KnowledgeError(422, "corrupt_pdf", "The PDF could not be read. Export a fresh copy and retry.") from exc

    if not any(page.text.strip() for page in pages):
        raise KnowledgeError(422, "no_pdf_text", "This PDF has no extractable text. Run OCR on scanned PDFs before uploading.")
    return pages
