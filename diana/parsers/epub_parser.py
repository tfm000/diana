from __future__ import annotations

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


class EPUBParser:
    supported_extensions = [".epub"]

    @staticmethod
    def chapter_count(file_path: str) -> int:
        """Return the number of document chapters (sections) in the EPUB."""
        book = epub.read_epub(file_path)
        count = sum(
            1 for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)
            if BeautifulSoup(item.get_content(), "html.parser").get_text(strip=True)
        )
        return count

    def extract_text(self, file_path: str, page_indices: list[int] | None = None) -> str:
        """Extract text from an EPUB.

        Args:
            file_path: Path to the EPUB file.
            page_indices: Optional 0-based chapter indices to extract.
                          If None or empty, all chapters are extracted.
        """
        book = epub.read_epub(file_path)
        chapters = []
        idx = 0
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = soup.get_text(separator="\n").strip()
            if text:
                if not page_indices or idx in page_indices:
                    chapters.append(text)
                idx += 1
        return "\n\n".join(chapters)
