"""Wave-0 RED/skip scaffolds for the generic resumable download layer (Plan 02).

The symbols under test (``download_file`` and ``has_space`` in
``diana.downloads.downloader``) do NOT exist yet — they land in Plan 02, which
flips every ``skipif`` below to a live regression gate with zero edits here.

Contract probed (RESEARCH Pattern 1 + 2, verified live against HuggingFace):
  download_file(url, dest, expected_md5=None, expected_size=None,
                progress=None, cancel=None) -> None
    - a ``.part`` of N bytes resumes via ``Range: bytes=N-``; a 206 appends, a
      200 resets the ``.part`` from scratch (server ignored Range)
    - md5 mismatch -> ``.part`` deleted, raises ValueError, no final file
    - md5 match    -> final file via ``os.replace``, ``.part`` gone (atomic)
  has_space(target, needed_bytes, margin=1.10) -> tuple[bool, int]
    - free < needed*margin -> (False, free); walks up to an existing ancestor

Every test stubs ``requests`` with a fake streaming response (mirrors
``test_piper_engine``'s mock-the-SDK idiom) and writes only into ``tmp_path`` —
no real network, no real cache dir is touched (threat T-04-01 / T-04-02).
ENGINE-02, D-05/06/07.
"""

import hashlib
from unittest.mock import MagicMock, patch

import pytest

# --- Guarded import: the downloader module lands in Plan 02 ------------------
try:
    from diana.downloads.downloader import download_file, has_space  # noqa: F401

    _DL_AVAILABLE = True
except ImportError:
    download_file = None  # type: ignore[assignment]
    has_space = None  # type: ignore[assignment]
    _DL_AVAILABLE = False


class _FakeResponse:
    """A minimal stand-in for the streaming ``requests`` response.

    Supports the context-manager + ``iter_content`` + ``headers`` +
    ``status_code`` + ``raise_for_status`` surface that Pattern 1 uses.
    """

    def __init__(self, body: bytes, status_code: int = 200, headers=None):
        self._body = body
        self.status_code = status_code
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=1 << 16):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i : i + chunk_size]


def _fake_requests(capture: dict, *, body: bytes, status_code: int, total: int):
    """Build a fake ``requests`` module whose ``get`` records the call.

    ``capture`` receives the ``headers`` the downloader sent (so a test can
    assert the resume ``Range`` header) and the streamed body is whatever the
    server returns for that (possibly ranged) request.
    """
    fake = MagicMock()

    def _get(url, headers=None, stream=True, timeout=None):
        capture["url"] = url
        capture["headers"] = headers or {}
        resp_headers = {"Content-Length": str(len(body))}
        if status_code == 206:
            start = total - len(body)
            resp_headers["Content-Range"] = f"bytes {start}-{total - 1}/{total}"
        return _FakeResponse(body, status_code=status_code, headers=resp_headers)

    fake.get = _get
    return fake


# --- ENGINE-02: resume offset -> Range header; 206 appends / 200 resets ------
@pytest.mark.skipif(not _DL_AVAILABLE, reason="downloader implemented in Plan 02")
def test_resume_offset(tmp_path):
    """A ``.part`` of N bytes resumes via ``Range: bytes=N-``; 206 appends."""
    full = b"0123456789ABCDEF" * 8  # 128 bytes
    dest = tmp_path / "voice.onnx"
    part = dest.with_name(dest.name + ".part")
    part.write_bytes(full[:50])  # 50 bytes already downloaded
    md5 = hashlib.md5(full).hexdigest()

    capture: dict = {}
    # Server honors Range -> 206, returns only the remaining tail.
    fake = _fake_requests(capture, body=full[50:], status_code=206, total=len(full))
    with patch("diana.downloads.downloader.requests", fake):
        download_file(str("http://x/voice.onnx"), dest, expected_md5=md5,
                      expected_size=len(full))

    assert capture["headers"].get("Range") == "bytes=50-", "must resume from offset 50"
    assert dest.read_bytes() == full, "206 tail must be appended to the .part"
    assert not part.exists(), "finalized .part is removed"


@pytest.mark.skipif(not _DL_AVAILABLE, reason="downloader implemented in Plan 02")
def test_status_200_resets_part(tmp_path):
    """When the server ignores Range (200), the ``.part`` is rewritten clean."""
    full = b"abcdefghij" * 10  # 100 bytes
    dest = tmp_path / "voice.onnx"
    part = dest.with_name(dest.name + ".part")
    part.write_bytes(b"STALE-PARTIAL-CONTENT")  # a stale partial that must be discarded
    md5 = hashlib.md5(full).hexdigest()

    capture: dict = {}
    fake = _fake_requests(capture, body=full, status_code=200, total=len(full))
    with patch("diana.downloads.downloader.requests", fake):
        download_file("http://x/voice.onnx", dest, expected_md5=md5,
                      expected_size=len(full))

    assert dest.read_bytes() == full, "200 response replaces the stale .part wholesale"
    assert not part.exists()


# --- ENGINE-02 / T-04-INT: md5 mismatch deletes the .part and raises ---------
@pytest.mark.skipif(not _DL_AVAILABLE, reason="downloader implemented in Plan 02")
def test_md5_mismatch_rejects(tmp_path):
    """Corrupt content -> ``.part`` deleted, ValueError raised, no final file."""
    body = b"corrupt-bytes-not-matching-the-manifest-md5"
    dest = tmp_path / "voice.onnx"
    part = dest.with_name(dest.name + ".part")

    capture: dict = {}
    fake = _fake_requests(capture, body=body, status_code=200, total=len(body))
    with patch("diana.downloads.downloader.requests", fake):
        with pytest.raises(ValueError):
            download_file("http://x/voice.onnx", dest,
                          expected_md5="0" * 32, expected_size=len(body))

    assert not dest.exists(), "no final file on md5 mismatch"
    assert not part.exists(), "corrupt .part is dropped"


# --- ENGINE-02 / T-04-INT: md5 match -> atomic os.replace finalize -----------
@pytest.mark.skipif(not _DL_AVAILABLE, reason="downloader implemented in Plan 02")
def test_atomic_finalize(tmp_path):
    """Matching md5 -> final file exists (via os.replace); ``.part`` is gone."""
    body = b"the-real-voice-model-bytes" * 4
    dest = tmp_path / "voice.onnx"
    part = dest.with_name(dest.name + ".part")
    md5 = hashlib.md5(body).hexdigest()

    capture: dict = {}
    fake = _fake_requests(capture, body=body, status_code=200, total=len(body))
    with patch("diana.downloads.downloader.requests", fake):
        download_file("http://x/voice.onnx", dest, expected_md5=md5,
                      expected_size=len(body))

    assert dest.is_file() and dest.read_bytes() == body
    assert not part.exists()


# --- ENGINE-02 / D-05 / T-04-DISK: disk-space pre-check refuses ---------------
@pytest.mark.skipif(not _DL_AVAILABLE, reason="has_space implemented in Plan 02")
def test_disk_precheck(tmp_path):
    """free < needed*margin -> ``has_space`` returns (False, free); else True."""
    Usage = MagicMock()
    # free = 100 bytes; need 200 -> insufficient.
    with patch("diana.downloads.downloader.shutil.disk_usage",
               return_value=MagicMock(free=100)):
        ok, free = has_space(tmp_path / "models" / "voice.onnx", 200)
    assert ok is False and free == 100

    # free = 10_000 bytes; need 100 (×1.10 margin = 110) -> sufficient.
    with patch("diana.downloads.downloader.shutil.disk_usage",
               return_value=MagicMock(free=10_000)):
        ok2, free2 = has_space(tmp_path / "models" / "voice.onnx", 100)
    assert ok2 is True and free2 == 10_000
