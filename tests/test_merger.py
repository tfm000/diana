"""Tests for diana.processing.merger."""

from unittest.mock import MagicMock, patch

import diana.processing.merger as merger_mod
from diana.processing.merger import merge_chunks


class TestMergeChunks:
    def test_single_chunk(self, tmp_path):
        with patch.object(merger_mod, "AudioSegment") as mock_audio_cls:
            mock_segment = MagicMock()
            mock_audio_cls.from_file.return_value = mock_segment
            mock_audio_cls.empty.return_value = MagicMock()
            mock_audio_cls.silent.return_value = MagicMock()

            combined = mock_audio_cls.empty.return_value
            combined.__iadd__ = MagicMock(return_value=combined)
            combined.__add__ = MagicMock(return_value=combined)

            output = str(tmp_path / "out.mp3")
            merge_chunks(["chunk1.wav"], output)

            mock_audio_cls.from_file.assert_called_once_with("chunk1.wav")
            combined.export.assert_called_once_with(output, format="mp3", bitrate="192k")

    def test_multiple_chunks_adds_silence(self, tmp_path):
        with patch.object(merger_mod, "AudioSegment") as mock_audio_cls:
            mock_seg1 = MagicMock(name="seg1")
            mock_seg2 = MagicMock(name="seg2")
            mock_audio_cls.from_file.side_effect = [mock_seg1, mock_seg2]

            combined = MagicMock()
            mock_audio_cls.empty.return_value = combined
            combined.__iadd__ = MagicMock(return_value=combined)
            combined.__add__ = MagicMock(return_value=combined)

            silence = MagicMock(name="silence")
            mock_audio_cls.silent.return_value = silence

            output = str(tmp_path / "out.mp3")
            merge_chunks(["a.wav", "b.wav"], output, gap_ms=300)

            mock_audio_cls.silent.assert_called_once_with(duration=300)
            assert mock_audio_cls.from_file.call_count == 2

    def test_empty_chunk_list(self, tmp_path):
        with patch.object(merger_mod, "AudioSegment") as mock_audio_cls:
            combined = MagicMock()
            mock_audio_cls.empty.return_value = combined
            mock_audio_cls.silent.return_value = MagicMock()

            output = str(tmp_path / "out.mp3")
            merge_chunks([], output)

            combined.export.assert_called_once()

    def test_output_directory_created(self, tmp_path):
        with patch.object(merger_mod, "AudioSegment") as mock_audio_cls:
            combined = MagicMock()
            mock_audio_cls.empty.return_value = combined
            mock_audio_cls.silent.return_value = MagicMock()
            combined.__iadd__ = MagicMock(return_value=combined)
            combined.__add__ = MagicMock(return_value=combined)
            mock_audio_cls.from_file.return_value = MagicMock()

            nested_dir = tmp_path / "sub" / "dir"
            output = str(nested_dir / "out.mp3")
            merge_chunks(["chunk.wav"], output)

            assert nested_dir.exists()

    def test_custom_bitrate(self, tmp_path):
        with patch.object(merger_mod, "AudioSegment") as mock_audio_cls:
            combined = MagicMock()
            mock_audio_cls.empty.return_value = combined
            mock_audio_cls.silent.return_value = MagicMock()

            output = str(tmp_path / "out.mp3")
            merge_chunks([], output, bitrate="320k")

            combined.export.assert_called_once_with(output, format="mp3", bitrate="320k")
