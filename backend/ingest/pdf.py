from pathlib import Path

import fitz


def extract_pdf_text(file_path: str | Path) -> list[dict[str, str | int]]:
    pages: list[dict[str, str | int]] = []
    with fitz.open(file_path) as document:
        for page_number, page in enumerate(document, start=1):
            pages.append({"text": page.get_text("text").strip(), "page": page_number})
    return pages