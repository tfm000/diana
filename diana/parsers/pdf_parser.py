import fitz  # PyMuPDF


class PDFParser:
    supported_extensions = [".pdf"]

    def extract_text(self, file_path: str) -> str:
        doc = fitz.open(file_path)
        pages = []
        for page in doc:
            text = page.get_text("text").strip()
            if text:
                pages.append(text)
        doc.close()
        return "\n\n".join(pages)
