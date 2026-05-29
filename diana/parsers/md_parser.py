from markdown import markdown
from bs4 import BeautifulSoup

# Block-level tags that should produce a paragraph break after their text.
# Inline emphasis (strong, em, a, code, span) is intentionally excluded so it
# joins flush with surrounding prose — otherwise the rule-based cleaner mistakes
# the resulting short lines for chart fragments and drops them.
_BLOCK_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6",
               "p", "li", "blockquote", "pre", "tr")


class MDParser:
    supported_extensions = [".md"]

    def extract_text(self, file_path: str, page_indices=None) -> str:
        with open(file_path, "rb") as f:
            raw = f.read()

        text = None
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            text = raw.decode("utf-8", errors="replace")

        html = markdown(text, extensions=["extra"])
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(_BLOCK_TAGS):
            tag.append("\n\n")
        return soup.get_text(separator="").strip()
