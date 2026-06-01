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

# Curated low-ambiguity abbreviations → spoken words (CLEAN-06). Keys are regex
# fragments with escaped dots; each is applied with a (?<![A-Za-z]) lookbehind so
# it never fires mid-word (Drone. stays Drone.) and the required trailing period
# blocks bare tokens (the word "Mr" alone is left). Deliberately conservative:
# ambiguous units (m, kg, mi) and St. (Saint vs Street) are NOT here — they are
# left for the TTS engine, honoring the no-over-expansion criterion.
_ABBREVIATIONS = {
    r"Dr\.": "Doctor", r"Mr\.": "Mister", r"Mrs\.": "Missus", r"Ms\.": "Miz",
    r"Prof\.": "Professor", r"e\.g\.": "for example", r"i\.e\.": "that is",
    r"etc\.": "et cetera", r"vs\.": "versus", r"approx\.": "approximately",
    r"cf\.": "compare",
}

# Section/heading words that must survive chart-fragment cluster removal — a
# stack of these (Introduction / Methods / Results) is a heading list, not chart
# noise. Extends the original Chapter|Section|Part protection.
_SECTION_WORDS = re.compile(
    r"^(?:Chapter|Section|Part|Introduction|Methods?|Results?|Discussion|"
    r"Conclusion|Abstract|Appendix)\b",
    re.IGNORECASE,
)

# Non-decomposing Latin letters → ASCII (NFKD leaves these intact, so they need
# an explicit map). Used by _transliterate_ascii for ASCII-only engines so e.g.
# Straße → Strasse rather than losing the ß. Combining-diacritic letters
# (é, ï, ü, ç …) are handled by NFKD and are deliberately NOT listed here.
_TRANSLIT_SUPP = {
    "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE",
    "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L",
    "ð": "d", "Ð": "D", "þ": "th", "Þ": "Th",
}

# Inline-math span matcher for _remove_inline_math. Bounded {1,200} over a
# negated [^$\n] class — no nested unbounded repetition, so no catastrophic
# backtracking (ReDoS mitigation, T-02-01; verified linear on 100k adversarial
# '$' input). Currency normalization runs BEFORE this, so by the time it sees
# the text every real '$5'/'$10' has already become "5 dollars"/"10 dollars" —
# nothing currency-shaped is left for it to mis-pair.
_INLINE_MATH_RE = re.compile(r"\$([^$\n]{1,200}?)\$")


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
    # Currency/percent MUST run before the inline-math remover (proven: else
    # "$5 and $10" → "10"). It removes every '$' so nothing mis-pairs.
    text = _normalize_currency_percent(text)
    text = _remove_inline_math(text)
    text = _remove_citations(text)
    text = _remove_figure_table_refs(text)
    # Code blocks MUST come out BEFORE table/chart detection: code lines are
    # short and symbol-heavy and would false-trigger those noise detectors.
    text = _remove_code_blocks(text)
    text = _remove_tables(text)
    text = _remove_chart_fragments(text)
    # List-marker strip runs AFTER chart detection so the markers are still
    # visible for the chart/heading protection; it keeps the item prose.
    text = _strip_list_markers(text)
    text = _remove_common_footers(text)
    # Abbreviations expand BEFORE URL/email stripping so dotted tokens
    # (e.g./i.e./U.S.) are already words before any later URL pass.
    text = _expand_abbreviations(text)
    text = _strip_urls(text)
    text = _normalize_unicode(text)
    text = _remove_repeated_lines(text)
    text = _remove_page_numbers(text, source_format)
    if ascii_only:
        # Transliterate THEN net — café->cafe (never caf); both skipped for
        # UTF-8-capable engines so real accents survive.
        text = _transliterate_ascii(text)
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


def _normalize_currency_percent(text: str) -> str:
    """Currency/percent symbols → spoken words, digits preserved (CLEAN-06).

    Substitution order matters: the cents form ($5.50) must run before the bare
    dollar form ($5) so "$5.50" is not partially consumed as "$5". Only the
    SYMBOL becomes a word — the digits are kept verbatim (no number-to-words;
    VNEXT-03 stays deferred and the TTS engine vocalizes "5", "50", etc.).

    This MUST run BEFORE _remove_inline_math (the single load-bearing ordering
    constraint of the phase): the old inline-math remover paired the first '$'
    with the next, so "$5 and $10" → "10" (currency eaten). Converting currency
    first removes every '$', so nothing math-shaped is left to mis-pair.
    Pure: re-only, no logging/exceptions.
    """
    text = re.sub(r"\$(\d+)\.(\d{2})\b", r"\1 dollars and \2 cents", text)  # cents first
    text = re.sub(r"\$(\d+(?:,\d{3})*)\b", r"\1 dollars", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"\1 percent", text)
    text = re.sub(r"£(\d+(?:,\d{3})*)\b", r"\1 pounds", text)
    text = re.sub(r"€(\d+(?:,\d{3})*)\b", r"\1 euros", text)
    return text


def _remove_inline_math(text: str) -> str:
    """Strip inline $...$ math (math-aware) plus stray LaTeX commands/braces.

    A $...$ span is dropped only when its inner text carries a math signal
    ([A-Za-z\\^_=+<>/]) — so a rare currency-shaped leftover would be kept
    rather than blindly eaten. In practice _normalize_currency_percent has
    already removed every currency '$' before this runs, so the only $-spans
    reaching here are genuine math (e.g. "$x + y$").

    The stray-command and stray-brace removal that was the back half of the old
    _remove_remaining_latex stays here so \\textbf{...}-content survival and
    \\command / { } stripping keep working.
    """
    def repl(m: re.Match) -> str:
        inner = m.group(1)
        if re.search(r"[A-Za-z\\^_=+<>/]", inner):  # math signal → real math
            return ""
        return m.group(0)  # keep (rare currency-shaped leftover)

    text = _INLINE_MATH_RE.sub(repl, text)
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


def _remove_code_blocks(text: str) -> str:
    """Remove fenced and clearly-indented code blocks — unspeakable (CLEAN-05).

    Two passes, both conservative per CLEAN-07:

    1. Fenced blocks delimited by triple-backtick fences are removed regardless
       of length (the fence markers are unambiguous). The span matcher is a
       BOUNDED inner match — ``` then a negated-fence run then ``` — not a nested
       unbounded `.*`, so there is no catastrophic backtracking (ReDoS, T-02-01).
       Mirrors `_remove_latex_display`'s DOTALL-span idiom.
    2. Indented code: a CONTIGUOUS run of 2+ lines each indented by 4+ spaces or
       a leading tab is dropped (a real code block). A SINGLE indented line is
       KEPT — it is far more likely indented prose (a quote, a wrapped sentence,
       a hanging indent) than code. Line-oriented split/keep/join, mirroring
       `_remove_tables`. The anchored `^( {4,}|\\t)` test is bounded (no nested
       unbounded repetition).

    Runs BEFORE table/chart detection (stage step 8): code lines are short and
    symbol-heavy and would false-trigger those noise detectors. Pure: re-only,
    no logging/exceptions.
    """
    # 1. Fenced blocks (``` ... ```). Bounded inner: any run of non-backtick
    # chars, or a backtick not part of a closing fence — never nested unbounded.
    text = re.sub(r"```[^\n`]*\n(?:[^`]|`(?!``))*```", "", text, flags=re.DOTALL)

    # 2. Contiguous indented (4+ spaces or tab) runs of 2+ lines.
    lines = text.split("\n")
    keep = [True] * len(lines)
    i = 0
    while i < len(lines):
        if re.match(r"^( {4,}|\t)", lines[i]):
            j = i
            while j < len(lines) and re.match(r"^( {4,}|\t)", lines[j]):
                j += 1
            if j - i >= 2:  # real code block (>=2 contiguous indented lines)
                for k in range(i, j):
                    keep[k] = False
            i = j
        else:
            i += 1
    return "\n".join(line for line, k in zip(lines, keep) if k)


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


def _strip_list_markers(text: str) -> str:
    """Strip a leading list marker, keep the item PROSE (CLEAN-05).

    Line-oriented. Removes a leading bullet (`- `, `* `, `+ `), ordered-numeric
    (`1. `/`12. `), or ordered-alpha (`a) `/`A) `) marker and keeps the remaining
    item text — the line is NEVER deleted. Bounded anchored patterns
    (`^\\s*[-*+]\\s+`, `^\\s*\\d{1,3}[.)]\\s+`, `^\\s*[A-Za-z][.)]\\s+`); the
    `\\d{1,3}` and single-letter classes mean no nested unbounded repetition
    (ReDoS, T-02-01).

    Runs AFTER `_remove_chart_fragments` (hard constraint): the chart/heading
    protection in 02-01 must still see the markers to protect list items —
    stripping them earlier would blind that protection. Pure: re-only, no
    logging/exceptions.
    """
    lines = text.split("\n")
    out = []
    for line in lines:
        # Bullet, then ordered-numeric, then ordered-alpha — first match wins.
        stripped = re.sub(r"^\s*[-*+]\s+", "", line)
        if stripped == line:
            stripped = re.sub(r"^\s*\d{1,3}[.)]\s+", "", line)
        if stripped == line:
            stripped = re.sub(r"^\s*[A-Za-z][.)]\s+", "", line)
        out.append(stripped)
    return "\n".join(out)


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


def _expand_abbreviations(text: str) -> str:
    """Expand the curated abbreviation set to spoken words (CLEAN-06).

    Each entry is applied as re.sub(r"(?<![A-Za-z])" + pat, rep, text): the
    leading-letter lookbehind prevents mid-word matches (Drone. stays Drone.)
    and the required trailing period in every pattern prevents matching a bare
    token (the word "Mr" alone is left). No capitalization fix-up after
    expansion — the TTS engine handles a lowercase sentence start, keeping v1
    minimal (RESEARCH Flagged #5). Runs BEFORE URL/email stripping so dotted
    tokens like e.g./U.S. are already words before any later URL pass. Pure.
    """
    for pat, rep in _ABBREVIATIONS.items():
        text = re.sub(r"(?<![A-Za-z])" + pat, rep, text)
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


def _transliterate_ascii(text: str) -> str:
    """Fold non-ASCII characters to their nearest ASCII form (ASCII-only engines).

    Per character: pass ASCII through unchanged; map non-decomposing letters via
    _TRANSLIT_SUPP (ß→ss, æ→ae, …); otherwise NFKD-normalize and keep only
    non-combining ASCII codepoints — so café→cafe, naïve→naive, Zürich→Zurich,
    Straße→Strasse, and an undecomposable character (e.g. CJK) becomes empty
    rather than partial garbage. This runs before strip_non_speakable so accents
    are transliterated, never truncated (café→cafe, never caf). Pure: per-char
    loop + unicodedata, no regex (no ReDoS surface).
    """
    out = []
    for ch in text:
        if ord(ch) < 128:
            out.append(ch)
        elif ch in _TRANSLIT_SUPP:
            out.append(_TRANSLIT_SUPP[ch])
        else:
            decomposed = unicodedata.normalize("NFKD", ch)
            out.append(
                "".join(
                    c for c in decomposed
                    if not unicodedata.combining(c) and ord(c) < 128
                )
            )
    return "".join(out)


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
