from typing import Protocol


class FileParser(Protocol):
    """Protocol that all file parsers must implement."""

    @property
    def supported_extensions(self) -> list[str]:
        """File extensions this parser handles, e.g. ['.pdf']."""
        ...

    def extract_text(self, file_path: str) -> str:
        """Extract all text content from the given file.

        Returns the full text as a single string with paragraph breaks preserved.
        """
        ...
