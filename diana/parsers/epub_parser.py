import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


class EPUBParser:
    supported_extensions = [".epub"]

    def extract_text(self, file_path: str) -> str:
        book = epub.read_epub(file_path)
        chapters = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = soup.get_text(separator="\n").strip()
            if text:
                chapters.append(text)
        return "\n\n".join(chapters)
