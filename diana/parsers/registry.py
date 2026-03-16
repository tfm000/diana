from pathlib import Path

from diana.parsers.pdf_parser import PDFParser
from diana.parsers.epub_parser import EPUBParser
from diana.parsers.txt_parser import TXTParser

_PARSERS = {
    ".pdf": PDFParser,
    ".epub": EPUBParser,
    ".txt": TXTParser,
}


def get_parser(file_path: str):
    """Return the appropriate parser for the given file path."""
    ext = Path(file_path).suffix.lower()
    cls = _PARSERS.get(ext)
    if cls is None:
        raise ValueError(f"Unsupported file format: {ext}")
    return cls()
