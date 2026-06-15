"""Opt-in real-network smoke for the resumable downloader (Plan 02).

Excluded by default — runs only under ``-m network`` (the marker is registered
in ``pyproject.toml``: ``markers = ["network: ..."]``). The download symbol is
import-guarded too, so collection stays GREEN before Plan 02 lands.

Verifies the live HuggingFace path that RESEARCH Pattern 1 was proven against:
the 4885-byte ``en_US-lessac-medium.onnx.json`` (md5
``c1f2b7bddefe113f3255ff9ef234cfd3``). It seeds a partial ``.part`` first so the
real request must resume via ``Range`` (206) rather than restart, then asserts
the finalized file's size + md5 match the manifest.

Threat T-04-02: this test must NEVER run unattended in CI — the ``network``
marker is excluded by the default selection; only an explicit ``-m network`` opt-in
runs it. ENGINE-02 (real resumable download + integrity verify over HTTPS/TLS).
"""

import hashlib

import pytest

# --- Guarded import: the downloader module lands in Plan 02 ------------------
try:
    from diana.downloads.downloader import download_file  # noqa: F401

    _DL_AVAILABLE = True
except ImportError:
    download_file = None  # type: ignore[assignment]
    _DL_AVAILABLE = False

# The small, stable real asset verified live in RESEARCH (Pattern 1).
_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
    "en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
)
_EXPECTED_MD5 = "c1f2b7bddefe113f3255ff9ef234cfd3"
_EXPECTED_SIZE = 4885


@pytest.mark.network
@pytest.mark.skipif(not _DL_AVAILABLE, reason="downloader implemented in Plan 02")
def test_real_resumable_download(tmp_path):
    """Really fetch the lessac config from HF, resuming from a seeded ``.part``."""
    dest = tmp_path / "en_US-lessac-medium.onnx.json"
    part = dest.with_name(dest.name + ".part")

    # Seed a partial so the live request must use Range/206 to finish (resume,
    # not restart) — the exact behavior verified live in RESEARCH.
    part.write_bytes(b"\x00" * 1000)

    download_file(_URL, dest, expected_md5=_EXPECTED_MD5, expected_size=_EXPECTED_SIZE)

    assert dest.is_file(), "finalized file must exist after a resumed download"
    data = dest.read_bytes()
    assert len(data) == _EXPECTED_SIZE
    assert hashlib.md5(data).hexdigest() == _EXPECTED_MD5
    assert not part.exists(), "the .part is consumed by the atomic finalize"
