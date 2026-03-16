import re

# Split after sentence-ending punctuation followed by whitespace
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, max_chars: int = 4000) -> list[str]:
    """Split text into chunks respecting natural boundaries.

    Priority: paragraph breaks > sentence breaks > word breaks.
    Each chunk is guaranteed to be <= max_chars.
    """
    text = text.strip()
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    # First pass: split on paragraph boundaries (double newlines)
    paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current = ""

    for para in paragraphs:
        # If adding this paragraph fits, accumulate
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= max_chars:
            current = candidate
            continue

        # Current chunk is full — flush it if non-empty
        if current:
            chunks.append(current)
            current = ""

        # If the paragraph itself fits in one chunk, use it
        if len(para) <= max_chars:
            current = para
            continue

        # Paragraph too long — split on sentences
        sentences = _SENTENCE_RE.split(para)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate) <= max_chars:
                current = candidate
                continue

            if current:
                chunks.append(current)
                current = ""

            # If a single sentence is still too long, split on words
            if len(sentence) <= max_chars:
                current = sentence
            else:
                chunks.extend(_split_by_words(sentence, max_chars))

    if current:
        chunks.append(current)

    return chunks


def _split_by_words(text: str, max_chars: int) -> list[str]:
    """Last-resort split: break on word boundaries."""
    words = text.split()
    chunks = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = word

    if current:
        chunks.append(current)

    return chunks
