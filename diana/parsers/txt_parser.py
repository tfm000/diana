import codecs


class TXTParser:
    supported_extensions = [".txt"]

    def extract_text(self, file_path: str, page_indices=None) -> str:
        # Detect and strip BOM if present
        with open(file_path, "rb") as f:
            raw = f.read()

        # Try UTF-8 BOM first, then UTF-8, then latin-1 as fallback
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue

        return raw.decode("utf-8", errors="replace")
