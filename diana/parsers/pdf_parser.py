from __future__ import annotations

import fitz  # PyMuPDF


class PDFParser:
    supported_extensions = [".pdf"]

    @staticmethod
    def page_count(file_path: str) -> int:
        """Return the total number of pages without extracting text."""
        doc = fitz.open(file_path)
        count = len(doc)
        doc.close()
        return count

    def extract_text(self, file_path: str, page_indices: list[int] | None = None) -> str:
        """Extract text from a PDF.

        Args:
            file_path: Path to the PDF file.
            page_indices: Optional 0-based page indices to extract.
                          If None or empty, all pages are extracted.
        """
        doc = fitz.open(file_path)
        indices = page_indices if page_indices else range(len(doc))
        pages = []
        for i in indices:
            if 0 <= i < len(doc):
                text = doc[i].get_text("text").strip()
                if text:
                    pages.append(text)
        doc.close()
        return "\n\n".join(pages)
