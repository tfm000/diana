"""Tests for diana.parsers (txt, pdf, epub)."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from diana.parsers.txt_parser import TXTParser


class TestTXTParser:
    def test_utf8_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Hello, world!", encoding="utf-8")
        result = TXTParser().extract_text(str(f))
        assert result == "Hello, world!"

    def test_utf8_bom_file(self, tmp_path):
        f = tmp_path / "bom.txt"
        f.write_bytes(b"\xef\xbb\xbfHello BOM")
        result = TXTParser().extract_text(str(f))
        assert result == "Hello BOM"

    def test_latin1_file(self, tmp_path):
        f = tmp_path / "latin.txt"
        f.write_bytes("caf\xe9".encode("latin-1"))
        result = TXTParser().extract_text(str(f))
        assert "caf" in result

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = TXTParser().extract_text(str(f))
        assert result == ""

    def test_page_indices_ignored(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("content", encoding="utf-8")
        result = TXTParser().extract_text(str(f), page_indices=[0, 1])
        assert result == "content"

    def test_supported_extensions(self):
        assert ".txt" in TXTParser.supported_extensions


class TestPDFParser:
    def _make_mock_doc(self, pages: list[str]):
        """Create a mock fitz document with given page texts."""
        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: len(pages)

        mock_pages = []
        for text in pages:
            page = MagicMock()
            page.get_text.return_value = text
            mock_pages.append(page)

        mock_doc.__getitem__ = lambda self, i: mock_pages[i]
        return mock_doc

    @patch("diana.parsers.pdf_parser.fitz")
    def test_extract_all_pages(self, mock_fitz):
        mock_fitz.open.return_value = self._make_mock_doc(["Page one.", "Page two."])
        from diana.parsers.pdf_parser import PDFParser

        result = PDFParser().extract_text("fake.pdf")
        assert "Page one." in result
        assert "Page two." in result

    @patch("diana.parsers.pdf_parser.fitz")
    def test_extract_specific_pages(self, mock_fitz):
        mock_fitz.open.return_value = self._make_mock_doc(["A", "B", "C"])
        from diana.parsers.pdf_parser import PDFParser

        result = PDFParser().extract_text("fake.pdf", page_indices=[0, 2])
        assert "A" in result
        assert "C" in result
        assert "B" not in result

    @patch("diana.parsers.pdf_parser.fitz")
    def test_page_count(self, mock_fitz):
        mock_fitz.open.return_value = self._make_mock_doc(["A", "B", "C"])
        from diana.parsers.pdf_parser import PDFParser

        assert PDFParser.page_count("fake.pdf") == 3

    @patch("diana.parsers.pdf_parser.fitz")
    def test_empty_pages_skipped(self, mock_fitz):
        mock_fitz.open.return_value = self._make_mock_doc(["Content", "  ", "More"])
        from diana.parsers.pdf_parser import PDFParser

        result = PDFParser().extract_text("fake.pdf")
        assert "Content" in result
        assert "More" in result

    @patch("diana.parsers.pdf_parser.fitz")
    def test_out_of_range_indices_skipped(self, mock_fitz):
        mock_fitz.open.return_value = self._make_mock_doc(["Only page"])
        from diana.parsers.pdf_parser import PDFParser

        result = PDFParser().extract_text("fake.pdf", page_indices=[0, 5])
        assert "Only page" in result

    def test_supported_extensions(self):
        from diana.parsers.pdf_parser import PDFParser

        assert ".pdf" in PDFParser.supported_extensions


class TestEPUBParser:
    def _make_mock_book(self, chapter_texts: list[str]):
        """Create a mock epub book with given chapter HTML content."""
        mock_book = MagicMock()
        items = []
        for text in chapter_texts:
            item = MagicMock()
            item.get_content.return_value = f"<html><body><p>{text}</p></body></html>".encode()
            items.append(item)
        mock_book.get_items_of_type.return_value = items
        return mock_book

    @patch("diana.parsers.epub_parser.epub")
    def test_extract_all_chapters(self, mock_epub):
        mock_epub.read_epub.return_value = self._make_mock_book(["Chapter 1", "Chapter 2"])
        from diana.parsers.epub_parser import EPUBParser

        result = EPUBParser().extract_text("fake.epub")
        assert "Chapter 1" in result
        assert "Chapter 2" in result

    @patch("diana.parsers.epub_parser.epub")
    def test_extract_specific_chapters(self, mock_epub):
        mock_epub.read_epub.return_value = self._make_mock_book(["A", "B", "C"])
        from diana.parsers.epub_parser import EPUBParser

        result = EPUBParser().extract_text("fake.epub", page_indices=[1])
        assert "B" in result
        assert "A" not in result
        assert "C" not in result

    @patch("diana.parsers.epub_parser.epub")
    def test_chapter_count(self, mock_epub):
        mock_epub.read_epub.return_value = self._make_mock_book(["A", "B"])
        from diana.parsers.epub_parser import EPUBParser

        assert EPUBParser.chapter_count("fake.epub") == 2

    @patch("diana.parsers.epub_parser.epub")
    def test_empty_chapters_skipped(self, mock_epub):
        mock_book = MagicMock()
        items = []
        for text in ["Content", "", "More"]:
            item = MagicMock()
            item.get_content.return_value = f"<html><body>{text}</body></html>".encode()
            items.append(item)
        mock_book.get_items_of_type.return_value = items
        mock_epub.read_epub.return_value = mock_book
        from diana.parsers.epub_parser import EPUBParser

        result = EPUBParser().extract_text("fake.epub")
        assert "Content" in result
        assert "More" in result

    def test_supported_extensions(self):
        from diana.parsers.epub_parser import EPUBParser

        assert ".epub" in EPUBParser.supported_extensions
