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


def clean_text(text: str) -> str:
    """Clean extracted text for TTS synthesis."""
    if not text:
        return ""

    text = _remove_latex_display(text)
    text = _simplify_latex_inline(text)
    text = _remove_remaining_latex(text)
    text = _remove_citations(text)
    text = _remove_figure_table_refs(text)
    text = _strip_urls(text)
    text = _normalize_unicode(text)
    text = _remove_repeated_lines(text)
    text = _remove_page_numbers(text)
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


def _remove_page_numbers(text: str) -> str:
    """Remove standalone page numbers (lines that are just a number)."""
    return re.sub(r"(?m)^\s*\d{1,4}\s*$", "", text)


def _collapse_whitespace(text: str) -> str:
    """Collapse excessive whitespace while preserving paragraph breaks."""
    # Collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces to one
    text = re.sub(r"[^\S\n]+", " ", text)
    return text
