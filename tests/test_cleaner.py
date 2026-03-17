"""Tests for diana.processing.cleaner."""

import pytest

from diana.processing.cleaner import clean_text


class TestCleanText:
    """Integration tests for the full cleaning pipeline."""

    def test_empty_input(self):
        assert clean_text("") == ""

    def test_plain_text_unchanged(self):
        text = "The quick brown fox jumps over the lazy dog."
        assert clean_text(text) == text

    def test_paragraphs_preserved(self):
        text = "First paragraph.\n\nSecond paragraph."
        assert clean_text(text) == text


class TestLatexDisplayRemoval:
    def test_dollar_dollar(self):
        assert clean_text("Before $$x^2 + y^2 = z^2$$ after") == "Before after"

    def test_bracket_math(self):
        assert clean_text(r"Before \[E = mc^2\] after") == "Before after"

    def test_equation_environment(self):
        text = r"Before \begin{equation}E = mc^2\end{equation} after"
        assert clean_text(text) == "Before after"

    def test_align_environment(self):
        text = r"Before \begin{align*}a &= b\end{align*} after"
        assert clean_text(text) == "Before after"


class TestLatexInlineSimplification:
    def test_frac(self):
        result = clean_text(r"The value is \frac{a}{b} here.")
        assert "a over b" in result

    def test_sqrt(self):
        result = clean_text(r"Compute \sqrt{x} now.")
        assert "square root of x" in result

    def test_x_squared(self):
        result = clean_text("We have x^2 here.")
        assert "x squared" in result

    def test_x_cubed(self):
        result = clean_text("We have x^3 here.")
        assert "x cubed" in result

    def test_superscript_braces(self):
        result = clean_text(r"x^{n} is used.")
        assert "x to the n" in result

    def test_sum_integral(self):
        result = clean_text(r"The \sum and \int are operators.")
        assert "sum" in result
        assert "integral" in result

    def test_greek_letters(self):
        result = clean_text(r"The angle \alpha plus \beta.")
        assert "alpha" in result
        assert "beta" in result

    def test_infinity(self):
        result = clean_text(r"Approaches \infty.")
        assert "infinity" in result


class TestRemainingLatexRemoval:
    def test_inline_math_removed(self):
        assert "x + y" not in clean_text("Before $x + y$ after")

    def test_textbf_content_kept(self):
        result = clean_text(r"This is \textbf{bold} text.")
        assert "bold" in result

    def test_stray_commands_removed(self):
        result = clean_text(r"Some \noindent text \newpage here.")
        assert "noindent" not in result
        assert "newpage" not in result

    def test_stray_braces_removed(self):
        result = clean_text("Some {text} with braces.")
        assert "{" not in result
        assert "}" not in result


class TestCitations:
    def test_numbered_single(self):
        assert clean_text("As shown [1] here.") == "As shown here."

    def test_numbered_range(self):
        assert clean_text("Results [1-5] show.") == "Results show."

    def test_numbered_list(self):
        assert clean_text("See [1, 2, 3] for details.") == "See for details."

    def test_author_year_brackets(self):
        result = clean_text("As shown [Smith et al., 2020] here.")
        assert "Smith" not in result

    def test_author_year_parens(self):
        result = clean_text("As shown (Smith et al., 2020) here.")
        assert "Smith" not in result


class TestFigureTableRefs:
    def test_figure_ref(self):
        result = clean_text("As shown in Figure 3 and Figure 12.")
        assert "Figure" not in result

    def test_fig_ref(self):
        result = clean_text("See Fig. 1 for details.")
        assert "Fig." not in result

    def test_table_ref(self):
        result = clean_text("Table 2 shows the results.")
        assert "Table 2" not in result

    def test_equation_ref(self):
        result = clean_text("From Eq. 5 we derive.")
        assert "Eq." not in result


class TestUrlStripping:
    def test_http_url(self):
        result = clean_text("Visit http://example.com for info.")
        assert "http" not in result

    def test_https_url(self):
        result = clean_text("See https://example.com/path?q=1 here.")
        assert "https" not in result


class TestTableRemoval:
    def test_pipe_table(self):
        text = "Before.\n| Col1 | Col2 | Col3 |\n|------|------|------|\n| a | b | c |\nAfter."
        result = clean_text(text)
        assert "Col1" not in result
        assert "Before" in result
        assert "After" in result

    def test_tab_separated_rows(self):
        text = "Before.\nName\tAge\tCity\nAlice\t30\tNYC\nAfter."
        result = clean_text(text)
        assert "Alice" not in result
        assert "Before" in result

    def test_numeric_data_rows(self):
        text = "Before.\n12.5 34.2 56.1 78.9\n11.3 22.4 33.5 44.6\nAfter."
        result = clean_text(text)
        assert "12.5" not in result
        assert "After" in result

    def test_prose_with_numbers_preserved(self):
        text = "The experiment showed 95% accuracy on 3 datasets."
        result = clean_text(text)
        assert "95%" in result


class TestChartFragments:
    def test_short_cluster_removed(self):
        text = "Before.\nX axis\nY axis\n0\n10\n20\nAfter paragraph here."
        result = clean_text(text)
        assert "X axis" not in result
        assert "Before" in result
        assert "After paragraph" in result

    def test_short_lines_with_punctuation_preserved(self):
        text = "First point.\nSecond point.\nThird point."
        result = clean_text(text)
        assert "First point" in result
        assert "Second point" in result

    def test_chapter_headings_preserved(self):
        text = "Chapter 1\nThis is a full sentence paragraph."
        result = clean_text(text)
        assert "Chapter 1" in result

    def test_two_short_lines_preserved(self):
        text = "Label A\nLabel B\nThis is normal text here."
        result = clean_text(text)
        assert "Label A" in result


class TestCommonFooters:
    def test_copyright(self):
        result = clean_text("Some text.\n© 2024 Some Publisher\nMore text.")
        assert "Publisher" not in result
        assert "Some text" in result

    def test_all_rights_reserved(self):
        result = clean_text("Content.\nAll rights reserved.\nMore content.")
        assert "All rights reserved" not in result

    def test_doi(self):
        result = clean_text("Content.\nDOI: 10.1234/something.5678\nMore content.")
        assert "DOI" not in result

    def test_arxiv(self):
        result = clean_text("Content.\narXiv:2301.12345\nMore content.")
        assert "arXiv" not in result

    def test_page_x_of_y(self):
        result = clean_text("Content.\nPage 3 of 15\nMore content.")
        assert "Page 3" not in result

    def test_normal_text_preserved(self):
        result = clean_text("The journal published interesting results.")
        assert "journal" in result


class TestUnicodeNormalization:
    def test_smart_quotes(self):
        result = clean_text("\u201cHello\u201d and \u2018world\u2019")
        assert '"Hello"' in result
        assert "'world'" in result

    def test_em_dash(self):
        result = clean_text("word\u2014another")
        assert "--" in result

    def test_ellipsis(self):
        result = clean_text("wait\u2026")
        assert "..." in result

    def test_zero_width_chars_removed(self):
        result = clean_text("hel\u200blo")
        assert result == "hello"

    def test_control_chars_removed(self):
        result = clean_text("hello\x00world")
        assert result == "helloworld"

    def test_newline_preserved(self):
        result = clean_text("line1\nline2")
        assert "\n" in result


class TestRepeatedLines:
    def test_repeated_header_removed(self):
        lines = ["Chapter Title"] * 5 + ["Actual content here."]
        result = clean_text("\n".join(lines))
        assert "Chapter Title" not in result
        assert "Actual content" in result

    def test_non_repeated_preserved(self):
        text = "Line one.\nLine two.\nLine three."
        assert "Line one" in clean_text(text)


class TestPageNumbers:
    def test_standalone_number_removed(self):
        result = clean_text("Some text.\n  42  \nMore text.")
        assert "42" not in result

    def test_number_in_text_preserved(self):
        result = clean_text("There are 42 items.")
        assert "42" in result


class TestStripNonSpeakable:
    def test_math_symbols_removed(self):
        result = clean_text("The value is \u2264 5.")
        assert "\u2264" not in result

    def test_accented_chars_removed(self):
        result = clean_text("The caf\u00e9 is open.")
        assert "\u00e9" not in result
        assert "caf" in result

    def test_emoji_removed(self):
        result = clean_text("Great job! \U0001f44d")
        assert "\U0001f44d" not in result
        assert "Great job" in result

    def test_basic_ascii_preserved(self):
        text = "Hello, world! This is a test: 123 (yes)."
        assert clean_text(text) == text


class TestWhitespaceCollapse:
    def test_multiple_newlines_collapsed(self):
        result = clean_text("Para one.\n\n\n\n\nPara two.")
        assert "\n\n\n" not in result
        assert "Para one." in result
        assert "Para two." in result

    def test_multiple_spaces_collapsed(self):
        result = clean_text("word    word")
        assert result == "word word"
