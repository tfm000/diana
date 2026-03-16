from pathlib import Path

from pydub import AudioSegment


def merge_chunks(
    chunk_paths: list[str],
    output_path: str,
    bitrate: str = "192k",
    gap_ms: int = 500,
) -> None:
    """Merge ordered audio chunk files into a single MP3.

    Args:
        chunk_paths: Ordered list of paths to audio files (WAV or MP3).
        output_path: Where to write the final MP3.
        bitrate: MP3 bitrate (e.g. "192k").
        gap_ms: Milliseconds of silence between chunks.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=gap_ms)

    for i, path in enumerate(chunk_paths):
        segment = AudioSegment.from_file(path)
        if i > 0:
            combined += silence
        combined += segment

    combined.export(output_path, format="mp3", bitrate=bitrate)
