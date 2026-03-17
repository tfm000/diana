from diana.processing.chunker import chunk_text


class TestChunkText:
    def test_empty_string(self):
        assert chunk_text("") == []

    def test_whitespace_only(self):
        assert chunk_text("   \n\n  ") == []

    def test_short_text_single_chunk(self):
        text = "Hello world."
        result = chunk_text(text, max_chars=100)
        assert result == [text]

    def test_splits_on_paragraphs(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        result = chunk_text(text, max_chars=30)
        assert len(result) >= 2
        assert all(len(c) <= 30 for c in result)

    def test_splits_on_sentences(self):
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        result = chunk_text(text, max_chars=40)
        assert len(result) >= 2
        assert all(len(c) <= 40 for c in result)

    def test_splits_on_words_as_last_resort(self):
        # A very long "sentence" without punctuation
        text = " ".join(["word"] * 100)
        result = chunk_text(text, max_chars=50)
        assert len(result) > 1
        assert all(len(c) <= 50 for c in result)

    def test_all_chunks_within_limit(self):
        text = "A" * 500 + "\n\n" + "B" * 500 + "\n\n" + "C" * 500
        result = chunk_text(text, max_chars=600)
        assert all(len(c) <= 600 for c in result)

    def test_preserves_all_text(self):
        text = "Hello world. This is a test.\n\nAnother paragraph here."
        result = chunk_text(text, max_chars=30)
        # All original words should appear in the output
        joined = " ".join(result)
        for word in text.split():
            assert word in joined

    def test_exact_boundary(self):
        text = "Hello"
        result = chunk_text(text, max_chars=5)
        assert result == ["Hello"]

    def test_single_long_word(self):
        text = "a" * 100
        result = chunk_text(text, max_chars=50)
        # Can't split a single word further than word-level
        # The word itself exceeds max_chars, so it goes through as-is
        assert len(result) >= 1
