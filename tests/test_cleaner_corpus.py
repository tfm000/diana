"""Two-layer golden-corpus regression suite for the rule-based cleaner (CLEAN-08).

Layer 1 — property invariants (`_invariants`): a small set of assertions run over
every committed snapshot input for cross-stage coverage. The invariant set is
assembled INCREMENTALLY across Phase 2: at Wave 1 only the removal stages that
already exist (tables, page numbers, footers, the ASCII net) are live, so this
file asserts ONLY (a) preservation invariants (headings/years/accents survive)
and (b) basic structural invariants that are already true (no pipe-table rows,
no dangling punctuation, no triple newlines). Removal invariants for URLs/emails
(02-03) and figure/footnote tokens (02-04) are added by those plans at the
clearly-marked extension point — adding them now would fail against Wave-1
fixtures that legitimately still carry those tokens.

Layer 2 — snapshot fixtures (`tests/fixtures/cleaner/*.in.txt` / `*.expected.txt`):
exact `clean_text(inp, source_format=fmt, ascii_only=flag) == expected` checks.

The suite is the loud-failure guard for ROADMAP criterion #4: reverting a Task-2
or Task-3 fix must turn a corpus test red with a legible diff.
"""

import re
from pathlib import Path

import pytest

from diana.processing.cleaner import clean_text

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "cleaner"


def _load_snapshot(name: str) -> tuple[str, str]:
    """Read a fixture's (input, expected) pair, normalising one trailing newline.

    clean_text() output is already stripped, so a trailing newline an editor may
    append to a fixture is not significant — strip it from both files.
    """
    inp = (_FIXTURE_DIR / f"{name}.in.txt").read_text().rstrip("\n")
    expected = (_FIXTURE_DIR / f"{name}.expected.txt").read_text().rstrip("\n")
    return inp, expected


# Snapshot registry: (name, source_format, ascii_only). The `name` is the fixture
# stem under tests/fixtures/cleaner/. Each tuple is exercised both as an exact
# snapshot assertion AND as an input to the cross-stage invariant sweep.
_SNAPSHOTS = [
    ("years_preserve", "txt", True),
    ("headings_preserve", "pdf", True),
    ("pagenumber_remove", "pdf", True),
    ("footer_remove", "pdf", True),
    ("table_remove", "pdf", True),
    # normalization (CLEAN-06, 02-02): currency/percent/abbreviation transforms.
    # Selected by `pytest -k normalization` via the dedicated class below; also
    # swept by the cross-stage invariant run over every snapshot.
    ("currency_dollars", "txt", True),
    ("currency_cents", "txt", True),
    ("currency_dual", "txt", True),
    ("percent_normalize", "txt", True),
    ("abbreviations_expand", "txt", True),
    # code_lists_urls (CLEAN-05, 02-03): code-block removal (fenced + contiguous
    # indented), single-indented-prose keep, list-marker strip, and URL/email
    # removal with the U.S./e.g. structural guard. Selected by
    # `pytest -k code_lists_urls`; also swept by the cross-stage invariant run
    # (which now asserts the no-URL/no-email removal invariant registered below).
    ("code_lists_urls", "txt", True),
    ("urls_emails_guard", "txt", True),
    # figures (CLEAN-01, 02-04): caption-keep (label+colon dropped, prose kept),
    # inline reference removal with dangling-grammar repair, and residual
    # image-filename strip. Two flavors: a PDF/ASCII case and an EPUB/UTF-8 case
    # (the EPUB image-artifact path runs on the ascii_only=False side, the way a
    # UTF-8-capable engine like Piper sees EPUB text). Selected by
    # `pytest -k figures`; also swept by the cross-stage invariant run (which now
    # asserts the no-figure-token removal invariant registered this wave).
    ("figures", "pdf", True),
    ("figures_epub", "epub", False),
    # footnotes (CLEAN-03, 02-04): superscript marker removal, `[n]` marker
    # removal (via _remove_citations), best-effort footnote-body block drop, and
    # numbered-list preservation. Selected by `pytest -k footnotes`; also swept
    # by the cross-stage invariant run.
    ("footnotes", "pdf", True),
]

# The CLEAN-06 fixture stems (the `-k normalization` selector resolves to this
# class). These are transforms (symbol/abbreviation → words), so per the
# incremental invariant contract this wave registers NO new removal invariant —
# the existing Wave-2-active _invariants still run over them via the cross-stage
# sweep; no-URL/email (02-03) and figure-token (02-04) invariants stay deferred.
_NORMALIZATION = [
    s for s in _SNAPSHOTS
    if s[0].startswith(("currency_", "percent_", "abbreviations_"))
]


def _invariants(out: str, *, ascii_only: bool = False) -> None:
    """Assert the Wave-1 invariant set holds for a cleaned string.

    Wave 1 (this plan, 02-01) asserts only what the stages landed so far
    guarantee:

    Structural (already true after Wave 1):
      - no surviving pipe-table row
      - no dangling artifact: " ,", "( )", double space, triple newline

    Engine-conditional ASCII:
      - when ascii_only, every codepoint is ASCII

    Preservation (the CLEAN-07 over-stripping guard) is asserted per-fixture in
    the snapshot tests and in the dedicated preservation tests below, not here,
    because not every snapshot input contains headings/years.

    ----------------------------------------------------------------------------
    Wave N adds (extension point — each later slice appends its removal invariant
    here AS IT IMPLEMENTS the stage; do NOT add these earlier or earlier-wave
    fixtures that still carry the tokens will fail):
      - 02-03 (CLEAN-05): no URL / no "www." / no "<user>@<host>.<tld>" email
            — REGISTERED below (this wave owns it); holds across all snapshots.
      - 02-04 (CLEAN-01/03): no figure/table reference token
            — REGISTERED below (this wave owns it; completes the removal set);
            holds across all snapshots now that captions/refs are handled.
    ----------------------------------------------------------------------------
    """
    # Structural removal invariants (live at Wave 1).
    assert not re.search(r"(?m)^\|.*\|$", out), f"pipe-table row leaked: {out!r}"
    assert " ," not in out, f"dangling space-comma: {out!r}"
    assert "( )" not in out, f"empty parens: {out!r}"
    assert "  " not in out, f"double space: {out!r}"
    assert "\n\n\n" not in out, f"triple newline: {out!r}"

    # Wave 3 adds (02-03, CLEAN-05): no surviving URL or email. This wave owns the
    # URL/email removal stages, so it registers the removal invariant here. It
    # holds across ALL committed snapshot inputs (no prior fixture planted a
    # URL/email).
    assert "http" not in out, f"URL leaked: {out!r}"
    assert "www." not in out, f"www. URL leaked: {out!r}"
    assert not re.search(r"\S+@\S+\.\S+", out), f"email leaked: {out!r}"

    # Wave 4 adds (02-04, CLEAN-01): no surviving figure/table reference token.
    # This wave owns the caption/reference handling, so it registers the final
    # removal invariant here — completing the removal-invariant set
    # (pipe-table + no-URL/email + no-figure-token + no-dangling). It holds
    # across ALL committed snapshot inputs.
    assert not re.search(r"\b(Figure|Table|Fig\.|Tab\.)\s*\d", out), (
        f"figure/table reference token leaked: {out!r}"
    )

    # Engine-conditional ASCII path.
    if ascii_only:
        assert all(ord(c) < 128 for c in out), f"non-ASCII in ascii_only output: {out!r}"


class TestSnapshotsPreserve:
    """Exact snapshot match for the preservation fixtures (CLEAN-07 / CLEAN-02)."""

    @pytest.mark.parametrize("name, fmt, ascii_only", [
        s for s in _SNAPSHOTS if "preserve" in s[0]
    ])
    def test_preserve_snapshot_exact(self, name, fmt, ascii_only):
        inp, expected = _load_snapshot(name)
        assert clean_text(inp, source_format=fmt, ascii_only=ascii_only) == expected


class TestSnapshotsHeadersFooters:
    """Exact snapshot match for the header/footer + page-number fixtures (CLEAN-02)."""

    @pytest.mark.parametrize("name, fmt, ascii_only", [
        s for s in _SNAPSHOTS if s[0] in ("pagenumber_remove", "footer_remove")
    ])
    def test_headers_footers_snapshot_exact(self, name, fmt, ascii_only):
        inp, expected = _load_snapshot(name)
        assert clean_text(inp, source_format=fmt, ascii_only=ascii_only) == expected


class TestSnapshotsTables:
    """Exact snapshot match for the table-removal fixture (CLEAN-04)."""

    @pytest.mark.parametrize("name, fmt, ascii_only", [
        s for s in _SNAPSHOTS if s[0] == "table_remove"
    ])
    def test_tables_snapshot_exact(self, name, fmt, ascii_only):
        inp, expected = _load_snapshot(name)
        assert clean_text(inp, source_format=fmt, ascii_only=ascii_only) == expected


class TestSnapshotsNormalization:
    """Exact snapshot match for the CLEAN-06 normalization fixtures (02-02).

    The class name carries the `normalization` token so the VALIDATION selector
    `pytest tests/test_cleaner_corpus.py -k normalization` resolves here. Covers
    $5→"5 dollars", $5.50→"5 dollars and 50 cents", the $5-and-$10 both-survive
    case (currency-before-inline-math), 50%→"50 percent", and Dr./Mr./e.g.
    expansion.
    """

    @pytest.mark.parametrize("name, fmt, ascii_only", _NORMALIZATION)
    def test_normalization_snapshot_exact(self, name, fmt, ascii_only):
        inp, expected = _load_snapshot(name)
        assert clean_text(inp, source_format=fmt, ascii_only=ascii_only) == expected

    @pytest.mark.parametrize("name, fmt, ascii_only", _NORMALIZATION)
    def test_normalization_invariants_hold(self, name, fmt, ascii_only):
        # Cross-stage: a currency/abbreviation case must still satisfy the
        # currently-active (Wave-2) invariants. No new removal invariant added.
        inp, _ = _load_snapshot(name)
        out = clean_text(inp, source_format=fmt, ascii_only=ascii_only)
        _invariants(out, ascii_only=ascii_only)


_CODE_LISTS_URLS = [
    s for s in _SNAPSHOTS if s[0] in ("code_lists_urls", "urls_emails_guard")
]


class TestSnapshotsCodeListsUrls:
    """Exact snapshot match for the CLEAN-05 code/lists/URLs fixtures (02-03).

    The class name carries the `code_lists_urls` token so the VALIDATION selector
    `pytest tests/test_cleaner_corpus.py -k code_lists_urls` resolves here. Covers
    fenced + contiguous-indented code removal, the single-indented-prose keep,
    list-marker stripping (item text preserved), http/www/email removal, and the
    U.S./e.g. structural guard (kept because they carry no scheme/www./'@').
    """

    @pytest.mark.parametrize("name, fmt, ascii_only", _CODE_LISTS_URLS)
    def test_code_lists_urls_snapshot_exact(self, name, fmt, ascii_only):
        inp, expected = _load_snapshot(name)
        assert clean_text(inp, source_format=fmt, ascii_only=ascii_only) == expected

    @pytest.mark.parametrize("name, fmt, ascii_only", _CODE_LISTS_URLS)
    def test_code_lists_urls_invariants_hold(self, name, fmt, ascii_only):
        # Cross-stage: the no-URL/no-email removal invariant (registered this
        # wave) must hold for these fixtures, plus all earlier invariants.
        inp, _ = _load_snapshot(name)
        out = clean_text(inp, source_format=fmt, ascii_only=ascii_only)
        _invariants(out, ascii_only=ascii_only)


_FIGURES = [s for s in _SNAPSHOTS if s[0].startswith("figures")]


class TestSnapshotsFigures:
    """Exact snapshot match for the CLEAN-01 figures fixture (02-04).

    The class name carries the `figures` token so the VALIDATION selector
    `pytest tests/test_cleaner_corpus.py -k figures` resolves here. Covers the
    caption branch (label+colon dropped, prose kept), the reference branch
    (inline token removed + dangling grammar repaired — no 'in ,' / '( )' /
    double space), and the residual image-filename strip.
    """

    @pytest.mark.parametrize("name, fmt, ascii_only", _FIGURES)
    def test_figures_snapshot_exact(self, name, fmt, ascii_only):
        inp, expected = _load_snapshot(name)
        assert clean_text(inp, source_format=fmt, ascii_only=ascii_only) == expected

    @pytest.mark.parametrize("name, fmt, ascii_only", _FIGURES)
    def test_figures_invariants_hold(self, name, fmt, ascii_only):
        # Cross-stage: the no-figure-token removal invariant (registered this
        # wave) must hold for this fixture, plus all earlier invariants (no
        # dangling ' ,' / '( )', no URL/email, etc.).
        inp, _ = _load_snapshot(name)
        out = clean_text(inp, source_format=fmt, ascii_only=ascii_only)
        _invariants(out, ascii_only=ascii_only)


_FOOTNOTES = [s for s in _SNAPSHOTS if s[0] == "footnotes"]


class TestSnapshotsFootnotes:
    """Exact snapshot match for the CLEAN-03 footnotes fixture (02-04).

    The class name carries the `footnotes` token so the VALIDATION selector
    `pytest tests/test_cleaner_corpus.py -k footnotes` resolves here. Covers
    superscript-digit marker removal, `[n]` marker removal (via _remove_citations),
    a best-effort footnote-body block drop, and numbered-list preservation (the
    20+-char gate keeps the short list items from being mistaken for bodies).
    """

    @pytest.mark.parametrize("name, fmt, ascii_only", _FOOTNOTES)
    def test_footnotes_snapshot_exact(self, name, fmt, ascii_only):
        inp, expected = _load_snapshot(name)
        assert clean_text(inp, source_format=fmt, ascii_only=ascii_only) == expected

    @pytest.mark.parametrize("name, fmt, ascii_only", _FOOTNOTES)
    def test_footnotes_invariants_hold(self, name, fmt, ascii_only):
        # Cross-stage: every active removal invariant (incl. no-figure-token and
        # no-URL/email) plus the structural invariants must hold for this fixture.
        inp, _ = _load_snapshot(name)
        out = clean_text(inp, source_format=fmt, ascii_only=ascii_only)
        _invariants(out, ascii_only=ascii_only)


class TestInvariantsAcrossSnapshots:
    """Run the invariant sweep over EVERY snapshot input (cross-stage coverage)."""

    @pytest.mark.parametrize("name, fmt, ascii_only", _SNAPSHOTS)
    def test_invariants_hold(self, name, fmt, ascii_only):
        inp, _ = _load_snapshot(name)
        out = clean_text(inp, source_format=fmt, ascii_only=ascii_only)
        _invariants(out, ascii_only=ascii_only)


class TestPreservationInvariants:
    """The CLEAN-07 over-stripping guard — both directions, ascii_only parametrized."""

    def test_preserve_heading_stack(self):
        out = clean_text(
            "Introduction\nMethods\nResults\nThe body paragraph follows here.",
            source_format="pdf",
        )
        assert "Introduction" in out
        assert "Methods" in out
        assert "Results" in out

    def test_preserve_year_list(self):
        out = clean_text(
            "Yearly totals:\n\n2019\n2020\n\nTotals climbed.", source_format="txt"
        )
        assert "2019" in out
        assert "2020" in out

    def test_preserve_accents_for_utf8_engine(self):
        # UTF-8-capable engine keeps the real accented form.
        assert "café" in clean_text("The café is open.", ascii_only=False)

    def test_transliterate_accents_for_ascii_engine(self):
        # ASCII engine transliterates, never truncates: cafe present, no bare "caf ".
        out = clean_text("The café is open.", ascii_only=True)
        assert "cafe" in out
        assert "caf " not in out
        assert all(ord(c) < 128 for c in out)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
