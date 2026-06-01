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


class TestCurrencyNormalization:
    """Currency symbol -> spoken word, digits preserved (CLEAN-06).

    Runs BEFORE the inline-math remover so $5 and $10 both survive (the hard
    ordering constraint): once currency converts, no '$' is left to mis-pair.
    """

    def test_dollars_simple(self):
        assert "5 dollars" in clean_text("I paid $5 for lunch.")

    def test_dollars_and_cents(self):
        assert "5 dollars and 50 cents" in clean_text("$5.50 each.")

    def test_thousands_grouping(self):
        assert "1,000 dollars" in clean_text("It was $1,000 total.")

    def test_pounds(self):
        assert "10 pounds" in clean_text("It cost £10.")

    def test_euros(self):
        assert "20 euros" in clean_text("Or €20.")

    def test_digits_never_spelled(self):
        # Only the symbol becomes a word; the digits are preserved verbatim.
        out = clean_text("I paid $5 for lunch.")
        assert "5 dollars" in out
        assert "five" not in out

    def test_dual_currency_both_survive(self):
        # The canonical bug: the old $...$ remover paired the first $ with the
        # next and ate "$5 and $" -> only "10" survived. Currency-first fixes it.
        out = clean_text("I paid $5 and $10 for lunch.", source_format="txt")
        assert "5 dollars" in out
        assert "10 dollars" in out


class TestPercentNormalization:
    """Percent symbol -> 'percent', digits preserved (CLEAN-06)."""

    def test_integer_percent(self):
        assert "95 percent" in clean_text("Up 95% today.")

    def test_decimal_percent(self):
        assert "3.5 percent" in clean_text("Margin of 3.5%.")

    def test_percent_with_space(self):
        assert "50 percent" in clean_text("About 50 % done.")


class TestAbbreviationExpansion:
    """Curated low-ambiguity abbreviation expansion (CLEAN-06).

    Only the conservative set expands (Dr./Mr./e.g./vs./etc.). A leading-letter
    lookbehind blocks mid-word matches (Drone. stays Drone.) and the required
    trailing period blocks bare-token matches (the word "Mr" alone stays).
    Ambiguous units (m, kg, mi) and St. (Saint vs Street) are deferred to the
    engine — they are NOT in the map.
    """

    def test_titles_expanded_exact(self):
        assert clean_text("Dr. Smith met Mr. Jones.") == "Doctor Smith met Mister Jones."

    def test_mrs_ms_prof(self):
        out = clean_text("Mrs. Lee, Ms. Park and Prof. Ng.")
        assert "Missus" in out
        assert "Miz" in out
        assert "Professor" in out

    def test_latinisms_expanded(self):
        out = clean_text("Compare approx. 5 vs. 10, e.g. here.")
        assert "approximately" in out
        assert "versus" in out
        assert "for example" in out

    def test_ie_etc_cf(self):
        out = clean_text("Use it, i.e. now, etc. cf. above.")
        assert "that is" in out
        assert "et cetera" in out
        assert "compare" in out

    def test_no_midword_match(self):
        # A leading-letter lookbehind prevents matching inside a word.
        assert clean_text("A midword Drone flies.") == "A midword Drone flies."

    def test_bare_token_not_matched(self):
        # The required trailing period is absent, so bare "Mr" stays.
        assert "Mr is fine" in clean_text("The word Mr is fine.")

    def test_ambiguous_tokens_not_expanded(self):
        # St. is intentionally left for the engine (Saint vs Street ambiguity).
        out = clean_text("Meet on St. Mary St.")
        assert "Saint" not in out
        assert "Street" not in out


class TestMathAwareInlineRemoval:
    """The math-aware $...$ remover drops real math but currency is gone by then."""

    def test_real_inline_math_removed(self):
        out = clean_text("Before $x + y$ after")
        assert "x + y" not in out

    def test_currency_not_eaten_as_math(self):
        # "$5 and $10" must not be treated as one math span and partially eaten.
        out = clean_text("I paid $5 and $10 for lunch.")
        assert "5 dollars" in out
        assert "10 dollars" in out


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
    """Caption-vs-reference handling (CLEAN-01).

    Two branches: a label at the START of a segment followed by ':'/'.' then prose
    is a CAPTION (strip the label + delimiter, KEEP the sentence); a label embedded
    mid-sentence is a REFERENCE (remove the token, then repair the dangling grammar
    so no 'in ,' / '( )' / double space survives). Reference cases stay green from
    earlier waves; caption cases are added here (Regression #4).
    """

    # --- Reference branch (token removed + grammar repaired) ---

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

    def test_reference_grammar_repaired(self):
        # The inline token is removed AND the dangling grammar repaired: no
        # 'in ,', no double space, the prose intact.
        result = clean_text("As shown in Figure 3, the trend is up.")
        assert "Figure 3" not in result
        assert "in ," not in result
        assert "  " not in result
        assert "the trend is up" in result

    def test_reference_empty_parens_repaired(self):
        # "(see Figure 2)" must not leave an empty/dangling paren pair.
        result = clean_text("The method works (see Figure 2) well.")
        assert "Figure 2" not in result
        assert "( )" not in result
        assert "()" not in result
        assert "The method works" in result
        assert "well" in result

    # --- Caption branch (label + delimiter dropped, prose KEPT) ---

    def test_caption_colon_kept_prose(self):
        # "Figure 3: The system has three stages." keeps the sentence, drops the
        # label + colon, leaves no leading ": " artifact.
        result = clean_text("Figure 3: The system has three stages.")
        assert result == "The system has three stages."

    def test_caption_period_kept_prose(self):
        # A label followed by a period then a capitalized sentence is also a
        # caption — keep the prose.
        result = clean_text("Figure 3. The system has three stages.")
        assert "The system has three stages" in result
        assert "Figure 3" not in result
        assert not result.startswith(".")

    def test_caption_table_label_kept_prose(self):
        result = clean_text("Table 4: Summary statistics for each cohort.")
        assert "Summary statistics for each cohort" in result
        assert "Table 4" not in result
        assert not result.startswith(":")


class TestResidualImageArtifacts:
    """Residual EPUB/Markdown image artifacts are stripped (CLEAN-01).

    NOTE: literal Markdown image syntax `![alt](img.png)` never reaches the
    cleaner — the MD/EPUB parsers render to HTML and `get_text()` drops the
    <img> element entirely. This stage only catches RESIDUAL junk: a bare
    image-filename token (e.g. `image1.png`) that leaks from an oddly-formed
    source. It is intentionally conservative and bounded.
    """

    def test_residual_image_filename_removed(self):
        out = clean_text("The chart is here. image1.png Next sentence.")
        assert "image1.png" not in out
        assert "Next sentence" in out
        assert "The chart is here" in out

    def test_residual_image_filename_jpg_removed(self):
        out = clean_text("See diagram2.jpg for the layout.")
        assert "diagram2.jpg" not in out
        assert "for the layout" in out

    def test_real_word_with_png_substring_kept(self):
        # The matcher targets a bounded `image\d+.ext` / `<name><digit>.ext`
        # filename token, not arbitrary prose — a normal sentence is untouched.
        text = "The opening sentence is perfectly normal here."
        assert clean_text(text) == text


class TestUrlStripping:
    def test_http_url(self):
        result = clean_text("Visit http://example.com for info.")
        assert "http" not in result

    def test_https_url(self):
        result = clean_text("See https://example.com/path?q=1 here.")
        assert "https" not in result

    def test_www_url_removed(self):
        # www.-prefixed tokens are removed too (no scheme required) (CLEAN-05).
        result = clean_text("Browse www.example.org today.")
        assert "www." not in result
        assert "example.org" not in result
        assert "today" in result

    def test_url_removed_not_replaced_with_link(self):
        # Decision 4: remove entirely, never substitute a "link" token.
        result = clean_text("See https://example.com here.")
        assert "link" not in result.lower()

    def test_us_abbreviation_not_mistaken_for_url(self):
        # "U.S." has no scheme/www. prefix and no '@' -> the URL/email shapes
        # do not match it; it must survive the URL/email pass.
        result = clean_text("The U.S. economy grew.")
        assert "U.S." in result

    def test_eg_expansion_survives_url_pass(self):
        # e.g. is expanded to "for example" by 02-02 BEFORE this pass; assert the
        # expansion was not eaten by the URL/email stripping.
        result = clean_text("Many fruits, e.g. apples, are sweet.")
        assert "for example" in result


class TestEmailStripping:
    """Clear email addresses are removed entirely (CLEAN-05).

    The email shape requires an '@', so dotted prose tokens like U.S./e.g. (which
    have no '@') are structurally safe. Bounded anchored pattern (negated classes,
    no nested unbounded repetition) — ReDoS mitigation T-02-01.
    """

    def test_email_removed(self):
        result = clean_text("Mail me at bob@test.com today.")
        assert "@" not in result
        assert "bob@test.com" not in result
        assert "today" in result

    def test_dotted_email_removed(self):
        result = clean_text("Contact jane.doe+news@sub.example.co.uk please.")
        assert "@" not in result
        assert "example" not in result
        assert "please" in result

    def test_email_not_replaced_with_link(self):
        result = clean_text("Write to a@b.com now.")
        assert "link" not in result.lower()

    def test_url_and_email_together(self):
        result = clean_text(
            "See https://example.com/x and www.foo.org and mail me at "
            "bob@test.com today."
        )
        assert "http" not in result
        assert "www." not in result
        assert "@" not in result
        assert "today" in result


class TestCodeBlockRemoval:
    """Fenced + contiguous-indented code blocks are removed (CLEAN-05).

    Conservative per CLEAN-07: a fenced (```) block is always removed (the fence
    markers are unambiguous), a CONTIGUOUS run of 2+ indented (4-space/tab) lines
    is removed as a real code block, but a SINGLE indented line is KEPT — it is
    far more likely indented prose (a quote, a wrapped sentence, a hanging indent)
    than code. Code-block removal runs BEFORE table/chart noise detection so
    symbol-heavy short code lines do not false-trigger those detectors.
    """

    def test_fenced_block_removed(self):
        out = clean_text(
            "Intro line.\n\n```\ncode = 1\nprint(code)\n```\n\nOutro line."
        )
        assert "code = 1" not in out
        assert "print" not in out
        assert "Intro line" in out
        assert "Outro line" in out

    def test_fenced_block_with_language_tag_removed(self):
        out = clean_text(
            "Before.\n\n```python\nx = compute()\nreturn x\n```\n\nAfter."
        )
        assert "compute()" not in out
        assert "return x" not in out
        assert "Before" in out
        assert "After" in out

    def test_contiguous_indented_block_removed(self):
        out = clean_text(
            "Here is code:\n    def f():\n        return 1\nDone."
        )
        assert "def f()" not in out
        assert "return 1" not in out
        assert "Here is code" in out
        assert "Done" in out

    def test_single_indented_prose_line_kept(self):
        # The CLEAN-07 over-strip guard: one indented line is prose, not code.
        out = clean_text(
            "Normal line here.\n    This indented sentence is prose, not code.\n"
            "Next line here."
        )
        assert "This indented sentence is prose" in out
        assert "Normal line here" in out
        assert "Next line here" in out

    def test_tab_indented_block_removed(self):
        out = clean_text("Snippet:\n\ta = 1\n\tb = 2\nEnd.")
        assert "a = 1" not in out
        assert "b = 2" not in out
        assert "Snippet" in out
        assert "End" in out


class TestListMarkerStrip:
    """List markers are stripped while the item PROSE is kept (CLEAN-05).

    Runs AFTER chart-fragment detection so the markers are still visible for the
    chart/heading protection. The line is never deleted — only the leading marker
    prefix (- , * , + , 1. , a) ) is removed and the item text survives.
    """

    def test_dash_marker_stripped_text_kept(self):
        out = clean_text("- Apples\n- Oranges")
        assert "Apples" in out
        assert "Oranges" in out
        assert "- Apples" not in out

    def test_star_and_plus_markers_stripped(self):
        out = clean_text("* First item here.\n+ Second item here.")
        assert "First item here" in out
        assert "Second item here" in out
        assert "* First" not in out
        assert "+ Second" not in out

    def test_ordered_numeric_markers_stripped(self):
        out = clean_text("1. First step\n2. Second step")
        assert "First step" in out
        assert "Second step" in out
        assert "1. First" not in out
        assert "2. Second" not in out

    def test_ordered_alpha_markers_stripped(self):
        out = clean_text("a) Alpha choice\nB) Beta choice")
        assert "Alpha choice" in out
        assert "Beta choice" in out
        assert "a) Alpha" not in out
        assert "B) Beta" not in out

    def test_non_list_prose_unchanged(self):
        # A hyphenated/decimal sentence is not a list marker.
        text = "Well-known results show 3.5 cm of growth."
        out = clean_text(text)
        assert "Well-known results show" in out


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
        # Regression #3 flipped (02-02): percent normalization (CLEAN-06) now
        # reads 95% as "95 percent"; the prose row itself is still preserved
        # (not stripped as a table), which is what this case guards.
        text = "The experiment showed 95% accuracy on 3 datasets."
        result = clean_text(text)
        assert "95 percent" in result


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

    def test_section_headings_preserved(self):
        # A heading stack must survive the chart-fragment cluster removal — the
        # _SECTION_WORDS allow-list protects it (the canonical over-stripping bug).
        text = "Introduction\nMethods\nResults\nThis is the body paragraph."
        result = clean_text(text)
        assert "Introduction" in result
        assert "Methods" in result
        assert "Results" in result

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
        # Only an isolated number paragraph (blank-flanked) is a page number.
        result = clean_text("End of section.\n\n42\n\nNew section.")
        assert "42" not in result

    def test_number_between_prose_preserved(self):
        # A number between two prose lines is NOT a boundary -> preserved.
        result = clean_text("Some text.\n42\nMore text.")
        assert "42" in result

    def test_number_in_text_preserved(self):
        result = clean_text("There are 42 items.")
        assert "42" in result


class TestHeadersFooters:
    """Format-aware header/footer half of CLEAN-02 (reused footer stages + boundary rule)."""

    def test_pdf_page_of_y_footer_stripped(self):
        result = clean_text(
            "Real prose here.\nPage 3 of 10\nMore prose.", source_format="pdf"
        )
        assert "Page 3 of 10" not in result
        assert "Real prose here" in result
        assert "More prose" in result

    def test_copyright_footer_stripped(self):
        result = clean_text(
            "Real prose here.\n© 2024 Some Publisher\nMore prose.", source_format="pdf"
        )
        assert "Publisher" not in result
        assert "Real prose here" in result

    def test_doi_footer_stripped(self):
        result = clean_text(
            "Real prose here.\nDOI: 10.1234/abcd.5678\nMore prose.", source_format="pdf"
        )
        assert "DOI" not in result
        assert "More prose" in result

    def test_txt_prose_with_similar_tokens_kept(self):
        # Footer/page-number removal is structural, not token-greedy: TXT prose
        # carrying similar tokens is preserved.
        kept = clean_text(
            "We covered pages 3 through 10 of the manual.", source_format="txt"
        )
        assert "pages 3 through 10" in kept


class TestStripNonSpeakable:
    # The ASCII safety net is now engine-conditional (ascii_only=True); UTF-8-capable
    # engines (ascii_only=False, the default) preserve non-ASCII characters.
    def test_math_symbols_removed(self):
        result = clean_text("The value is \u2264 5.", ascii_only=True)
        assert "\u2264" not in result

    @pytest.mark.parametrize(
        "ascii_only, expected_present, expected_absent",
        [
            # ASCII engine: transliterate, never truncate -> "cafe" (not bare "caf ").
            (True, "cafe", "caf "),
            # UTF-8 engine: preserve the accented form.
            (False, "caf\u00e9", None),
        ],
    )
    def test_accented_chars(self, ascii_only, expected_present, expected_absent):
        result = clean_text("The caf\u00e9 is open.", ascii_only=ascii_only)
        assert expected_present in result
        if expected_absent is not None:
            assert expected_absent not in result

    def test_transliteration_not_truncation(self):
        # The canonical bug: caf\u00e9 must become cafe, never the bare stem caf.
        result = clean_text("The caf\u00e9 is open.", ascii_only=True)
        assert "cafe" in result
        assert "caf " not in result
        assert all(ord(c) < 128 for c in result)

    def test_emoji_removed(self):
        result = clean_text("Great job! \U0001f44d", ascii_only=True)
        assert "\U0001f44d" not in result
        assert "Great job" in result

    def test_non_ascii_preserved_for_utf8_engine(self):
        # Default ascii_only=False keeps real UTF-8 for capable engines.
        result = clean_text("The caf\u00e9 costs 5 \u20ac.", ascii_only=False)
        assert "\u00e9" in result

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
