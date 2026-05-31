"""Rule-based text cleaning for TTS synthesis.

Strips LaTeX, citations, URLs, control characters, and other content
that causes tokenizer errors in TTS engines.
"""

import re
import unicodedata
from collections import Counter

# Greek letter commands → spoken names
_GREEK_LETTERS = {
    r"\alpha": "alpha", r"\beta": "beta", r"\gamma": "gamma",
    r"\delta": "delta", r"\epsilon": "epsilon", r"\zeta": "zeta",
    r"\eta": "eta", r"\theta": "theta", r"\iota": "iota",
    r"\kappa": "kappa", r"\lambda": "lambda", r"\mu": "mu",
    r"\nu": "nu", r"\xi": "xi", r"\pi": "pi", r"\rho": "rho",
    r"\sigma": "sigma", r"\tau": "tau", r"\upsilon": "upsilon",
    r"\phi": "phi", r"\chi": "chi", r"\psi": "psi", r"\omega": "omega",
    r"\Alpha": "Alpha", r"\Beta": "Beta", r"\Gamma": "Gamma",
    r"\Delta": "Delta", r"\Theta": "Theta", r"\Lambda": "Lambda",
    r"\Pi": "Pi", r"\Sigma": "Sigma", r"\Phi": "Phi",
    r"\Psi": "Psi", r"\Omega": "Omega",
}

# Section/heading words that must survive chart-fragment cluster removal — a
# stack of these (Introduction / Methods / Results) is a heading list, not chart
# noise. Extends the original Chapter|Section|Part protection.
_SECTION_WORDS = re.compile(
    r"^(?:Chapter|Section|Part|Introduction|Methods?|Results?|Discussion|"
    r"Conclusion|Abstract|Appendix)\b",
    re.IGNORECASE,
)


def clean_text(text: str, *, source_format: str | None = None, ascii_only: bool = False) -> str:
    """Clean extracted text for TTS synthesis.

    Format-aware + engine-aware (Phase 2, Decision 5 — clean break, no shim):
    - source_format (pdf/epub/txt/md/web) drives format-sensitive stages
      (currently the page-number boundary rule).
    - ascii_only reflects the target engine's character capability
      (engine_is_ascii_only): when True the text is transliterated to ASCII
      (café->cafe) and the strip_non_speakable net runs; when False real UTF-8
      is preserved (café stays café) for UTF-8-capable engines.

    Both args are keyword-only with safe defaults so every existing
    positional clean_text(str) call still runs (format-agnostic, UTF-8-preserving).
    """
    if not text:
        return ""

    text = _remove_latex_display(text)
    text = _simplify_latex_inline(text)
    text = _remove_remaining_latex(text)
    text = _remove_citations(text)
    text = _remove_figure_table_refs(text)
    text = _remove_tables(text)
    text = _remove_chart_fragments(text)
    text = _remove_common_footers(text)
    text = _strip_urls(text)
    text = _normalize_unicode(text)
    text = _remove_repeated_lines(text)
    text = _remove_page_numbers(text, source_format)
    if ascii_only:
        text = strip_non_speakable(text)
    text = _collapse_whitespace(text)

    return text.strip()


def _remove_latex_display(text: str) -> str:
    """Remove display math: $$...$$, \\[...\\], \\begin{equation}...\\end{equation}."""
    # $$...$$ (display math)
    text = re.sub(r"\$\$.*?\$\$", "", text, flags=re.DOTALL)
    # \[...\] (display math)
    text = re.sub(r"\\\[.*?\\\]", "", text, flags=re.DOTALL)
    # \begin{equation}...\end{equation} and variants (align, gather, etc.)
    text = re.sub(
        r"\\begin\{(?:equation|align|gather|multline|eqnarray)\*?\}.*?"
        r"\\end\{(?:equation|align|gather|multline|eqnarray)\*?\}",
        "", text, flags=re.DOTALL,
    )
    return text


def _simplify_latex_inline(text: str) -> str:
    """Convert common inline LaTeX patterns to spoken equivalents."""
    # \frac{a}{b} → "a over b"
    text = re.sub(r"\\frac\{([^}]*)\}\{([^}]*)\}", r"\1 over \2", text)
    # \sqrt{x} → "square root of x"
    text = re.sub(r"\\sqrt\{([^}]*)\}", r"square root of \1", text)
    # x^2 → "x squared"
    text = re.sub(r"(\w)\^2(?![0-9])", r"\1 squared", text)
    # x^3 → "x cubed"
    text = re.sub(r"(\w)\^3(?![0-9])", r"\1 cubed", text)
    # x^{n} or x^n → "x to the n"
    text = re.sub(r"(\w)\^\{([^}]*)\}", r"\1 to the \2", text)
    text = re.sub(r"(\w)\^(\w)", r"\1 to the \2", text)
    # Common operators
    text = re.sub(r"\\sum", "sum", text)
    text = re.sub(r"\\prod", "product", text)
    text = re.sub(r"\\int", "integral", text)
    text = re.sub(r"\\infty", "infinity", text)
    text = re.sub(r"\\pm", "plus or minus", text)
    text = re.sub(r"\\times", "times", text)
    text = re.sub(r"\\cdot", "times", text)
    text = re.sub(r"\\leq?", "less than or equal to", text)
    text = re.sub(r"\\geq?", "greater than or equal to", text)
    text = re.sub(r"\\neq?", "not equal to", text)
    text = re.sub(r"\\approx", "approximately", text)
    # Greek letters
    for cmd, spoken in _GREEK_LETTERS.items():
        text = text.replace(cmd, spoken)
    return text


def _remove_remaining_latex(text: str) -> str:
    """Strip any remaining inline $...$ math and stray LaTeX commands."""
    # Inline math $...$
    text = re.sub(r"\$[^$]*?\$", "", text)
    # Stray LaTeX commands like \textbf{...} → keep content
    text = re.sub(r"\\(?:textbf|textit|emph|text|mathrm|mathbf)\{([^}]*)\}", r"\1", text)
    # Other \commands (no braces) — remove the command, keep surrounding text
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    # Remove stray braces
    text = re.sub(r"[{}]", "", text)
    return text


def _remove_citations(text: str) -> str:
    """Remove citation markers."""
    # Numbered: [1], [1,2], [1-5], [1, 2, 3-5]
    text = re.sub(r"\[[\d,\s\-–]+\]", "", text)
    # Author-year in brackets: [Smith et al., 2020], [Smith 2020]
    text = re.sub(r"\[[A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4}[a-z]?\]", "", text)
    # Author-year in parens: (Smith et al., 2020)
    text = re.sub(r"\([A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4}[a-z]?\)", "", text)
    return text


def _remove_figure_table_refs(text: str) -> str:
    """Remove figure, table, and equation references."""
    text = re.sub(
        r"(?:Figure|Fig\.|Table|Tab\.|Equation|Eq\.|Algorithm|Alg\.)\s*\d+[\.\w]*",
        "", text, flags=re.IGNORECASE,
    )
    return text


def _is_structured_row(s: str) -> bool:
    """Whether a stripped line looks like one row of a structured table.

    True for pipe-wrapped rows, tab-separated rows (>=2 tabs), or space-separated
    rows that are mostly numeric tokens (>=3 tokens, >0.6 numeric fraction).
    """
    if re.match(r"^\|.*\|$", s):
        return True
    if s.count("\t") >= 2:
        return True
    tokens = s.split()
    if len(tokens) >= 3:
        numeric = sum(1 for t in tokens if re.fullmatch(r"[\d.,;:%+\-]+", t))
        if numeric / len(tokens) > 0.6:
            return True
    return False


def _remove_tables(text: str) -> str:
    """Remove tabular content only when it forms a real table block.

    Conservative (CLEAN-04): a numeric/structured run is dropped only when >=2
    adjacent structured rows form a block — so a lone number-rich sentence
    (e.g. "in 2019, 2020 and 2021 sales rose") is KEPT. Pipe tables and
    tab-separated rows still register as structured rows.
    """
    lines = text.split("\n")
    keep = [True] * len(lines)
    i = 0
    while i < len(lines):
        if _is_structured_row(lines[i].strip()):
            j = i
            while j < len(lines) and _is_structured_row(lines[j].strip()):
                j += 1
            if j - i >= 2:  # real table block (>=2 adjacent structured rows)
                for k in range(i, j):
                    keep[k] = False
            i = j
        else:
            i += 1
    return "\n".join(line for line, k in zip(lines, keep) if k)


def _is_numeric_line(s: str) -> bool:
    """Whether a stripped line is a single bare number (e.g. a year or axis tick)."""
    tokens = s.split()
    if not tokens:
        return False
    numeric = sum(1 for t in tokens if re.fullmatch(r"[\d.,:%+\-]+", t))
    return numeric / len(tokens) >= 0.6


def _is_chart_label(s: str) -> bool:
    """Whether a stripped line is a short non-sentence label (axis title, legend entry).

    A few tokens, under ~20 chars, no terminal punctuation — never a section word.
    Real prose ends in punctuation or runs longer. This is the signal that a
    numeric run is a CHART (ticks beside labels) rather than a data column or a
    year list (which carry no labels and must be preserved).
    """
    if _SECTION_WORDS.match(s):
        return False
    tokens = s.split()
    if not tokens:
        return False
    if _is_numeric_line(s):
        return False
    return len(tokens) <= 2 and len(s) < 20 and not s.endswith((".", "!", "?", ":"))


def _is_noise_line(s: str) -> bool:
    """Whether a stripped line is chart noise: a bare number (tick) or a short label.

    Protected (never noise): section/heading words and empty lines.
    """
    if _SECTION_WORDS.match(s):
        return False
    return _is_numeric_line(s) or _is_chart_label(s)


def _remove_chart_fragments(text: str) -> str:
    """Remove clusters of chart/graph text-extraction noise.

    Chart text extracted from PDFs tends to appear as clusters of axis labels,
    legend entries, and tick values. Conservative (CLEAN-07): a >=3-line cluster
    of noise lines is dropped only when it contains at least one short label
    (so it reads as a chart, ticks beside labels) — a heading stack
    (Introduction / Methods / Results), real-word lines, and a pure number/year
    list (e.g. 2019 / 2020 / 2021, which has no labels) are all preserved.
    A standalone numeric run is left to the table/page-number stages.
    """
    lines = text.split("\n")
    cleaned = []
    i = 0
    while i < len(lines):
        cluster_start = i
        while i < len(lines) and _is_noise_line(lines[i].strip()):
            i += 1
        cluster_len = i - cluster_start
        cluster = lines[cluster_start:i]
        has_label = any(_is_chart_label(line.strip()) for line in cluster)
        if cluster_len >= 3 and has_label:
            # Skip the cluster (a chart: tick values beside axis/legend labels).
            i = cluster_start + cluster_len
        else:
            # Keep the lines (too small, or a label-less number/year run).
            for line in cluster:
                cleaned.append(line)
            if i == cluster_start:
                cleaned.append(lines[i])
                i += 1
    return "\n".join(cleaned)


def _remove_common_footers(text: str) -> str:
    """Remove common footer/header patterns from extracted text."""
    # Each pattern removes the entire line it matches
    footer_patterns = [
        # Copyright lines
        r"^\s*(?:©|Copyright|\(c\))\s.*$",
        # "All rights reserved"
        r"^\s*All\s+rights\s+reserved\.?\s*$",
        # DOI lines
        r"^\s*(?:DOI|doi)\s*[:.]?\s*10\.\S+\s*$",
        # arXiv identifiers
        r"^\s*arXiv:\S+\s*$",
        # Journal / conference footers (e.g. "Proceedings of ...", "Journal of ...")
        r"^\s*(?:Proceedings|Journal|Transactions|Annals)\s+of\s+.*$",
        # "Published in ..." / "Accepted for ..."
        r"^\s*(?:Published|Accepted|Submitted|Received|Revised)\s+(?:in|for|by|on)\s.*$",
        # "Preprint" / "Draft" / "Under review"
        r"^\s*(?:Preprint|Draft|Under\s+review|Working\s+paper)\.?\s*$",
        # ISSN / ISBN lines
        r"^\s*(?:ISSN|ISBN)[\s:\-]*[\dX\-]+\s*$",
        # "Page X of Y" patterns
        r"^\s*[Pp]age\s+\d+\s+of\s+\d+\s*$",
    ]
    combined = "|".join(f"(?:{p})" for p in footer_patterns)
    text = re.sub(combined, "", text, flags=re.MULTILINE | re.IGNORECASE)
    return text


def _strip_urls(text: str) -> str:
    """Remove URLs."""
    text = re.sub(r"https?://\S+", "", text)
    return text


def _normalize_unicode(text: str) -> str:
    """Normalize Unicode and replace special characters with ASCII/spoken equivalents."""
    text = unicodedata.normalize("NFC", text)

    # Smart quotes → ASCII
    text = text.replace("\u201c", '"').replace("\u201d", '"')  # " "
    text = text.replace("\u2018", "'").replace("\u2019", "'")  # ' '

    # Dashes
    text = text.replace("\u2014", " -- ")   # em dash
    text = text.replace("\u2013", "-")      # en dash

    # Other common replacements
    text = text.replace("\u2026", "...")     # ellipsis
    text = text.replace("\u00a0", " ")      # non-breaking space
    text = text.replace("\u200b", "")       # zero-width space
    text = text.replace("\u200c", "")       # zero-width non-joiner
    text = text.replace("\u200d", "")       # zero-width joiner
    text = text.replace("\ufeff", "")       # BOM

    # Remove remaining control characters (Cc and Cf) except newline and tab
    text = "".join(
        ch for ch in text
        if ch in ("\n", "\t") or unicodedata.category(ch) not in ("Cc", "Cf")
    )
    return text


def _remove_repeated_lines(text: str, threshold: int = 3) -> str:
    """Remove lines that appear more than `threshold` times (headers/footers)."""
    lines = text.split("\n")
    counts = Counter(line.strip() for line in lines if line.strip())
    repeated = {line for line, count in counts.items() if count > threshold}
    if not repeated:
        return text
    filtered = [line for line in lines if line.strip() not in repeated]
    return "\n".join(filtered)


def _remove_page_numbers(text: str, source_format: str | None = None) -> str:
    """Remove standalone page numbers — only an isolated number paragraph.

    Conservative (CLEAN-02 page-number half): a 1-4 digit line is dropped only
    when both neighbours are blank or document edges, i.e. an isolated number
    paragraph. PDF pages are joined with "\\n\\n" (pdf_parser.py), so such
    isolated number paragraphs arise from PDF page structure, while TXT/EPUB
    prose keeps its inline numbers (years, chapter numbers, numeric list items)
    because they are not blank-flanked — so the same rule strips PDF page numbers
    without a parser change.

    source_format is accepted to document/guard the boundary intent and is
    reserved for a future form-feed (\\f) sentinel approach; parsers are out of
    scope for this phase, so it does not change behaviour here.
    """
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        s = line.strip()
        if re.fullmatch(r"\d{1,4}", s):
            prev_blank = (i == 0) or (lines[i - 1].strip() == "")
            next_blank = (i == len(lines) - 1) or (lines[i + 1].strip() == "")
            if prev_blank and next_blank:
                continue  # isolated number paragraph = page number
        out.append(line)
    return "\n".join(out)


# Characters safe for TTS: basic ASCII printable + newline/tab.
# Kokoro's ONNX tokenizer has a 510-token vocabulary and crashes on
# characters outside its expected range.
_SPEAKABLE_RE = re.compile(r"[^ -~\n\t]")


def strip_non_speakable(text: str) -> str:
    """Remove any character outside printable ASCII (plus newline/tab).

    This is a safety net after all other cleaning — anything that slipped
    through (math symbols, accented chars, emoji, etc.) gets dropped so the
    TTS tokenizer never sees an out-of-vocabulary character.
    """
    return _SPEAKABLE_RE.sub("", text)


def _collapse_whitespace(text: str) -> str:
    """Collapse excessive whitespace while preserving paragraph breaks."""
    # Collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces to one
    text = re.sub(r"[^\S\n]+", " ", text)
    return text
