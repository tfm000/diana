"""Wave-0 RED/skip scaffolds for voice uninstall + partial cleanup (Plan 04).

VOICE-07: a user can remove an installed voice and clean orphaned partial
downloads. D-17 blocks uninstall of an in-use voice — one referenced by a
non-terminal job's ``tts_voice`` OR equal to a stored
``tts.default_voice.<engine>`` value — and tells the user to switch first. D-18
adds a bulk ``*.part`` cleanup that clears orphaned partials in ``model_dir``.

The symbols (an in-use-block predicate + an uninstall action + a bulk-partial
cleanup) land in Plan 04; their module home and exact names are the
implementer's choice, so several candidates are probed. Tests use a real tmp
sqlite db (``test_database.py`` pattern) + a ``tmp_path`` ``model_dir`` — the
real cache is never touched (threat T-04-FILE). Collection stays GREEN until the
symbols land.
"""

import inspect

import pytest

from diana.database import create_job, init_db, set_setting
from diana.models import Job, JobStatus

# --- Guarded probes: uninstall helpers land in Plan 04 ----------------------
_voice_in_use = None
for _modname, _attr in (
    ("diana.tts.install_state", "voice_in_use"),
    ("diana.tts.registry", "voice_in_use"),
    ("diana.tts.install_state", "is_voice_in_use"),
    ("diana.tts.registry", "is_voice_in_use"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _voice_in_use = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue
_IN_USE_AVAILABLE = _voice_in_use is not None

_uninstall_voice = None
for _modname, _attr in (
    ("diana.tts.install_state", "uninstall_voice"),
    ("diana.tts.registry", "uninstall_voice"),
    ("diana.downloads.downloader", "uninstall_voice"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _uninstall_voice = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue
_UNINSTALL_AVAILABLE = _uninstall_voice is not None

_clean_partials = None
for _modname, _attr in (
    ("diana.downloads.downloader", "clean_partial_downloads"),
    ("diana.downloads.downloader", "clean_partials"),
    ("diana.tts.install_state", "clean_partial_downloads"),
    ("diana.tts.registry", "clean_partial_downloads"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _clean_partials = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue
_CLEAN_AVAILABLE = _clean_partials is not None


def _make_db(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    return db


def _call_in_use(db, engine, voice_id):
    """Call the in-use predicate tolerant of its (planner-chosen) signature.

    Supports either ``(db_path, engine, voice_id)`` or ``(db_path, voice_id)``.
    """
    params = inspect.signature(_voice_in_use).parameters
    if len(params) >= 3:
        return _voice_in_use(db, engine, voice_id)
    return _voice_in_use(db, voice_id)


# --- VOICE-07 / D-17: in-use block (job-reference arm + default-key arm) -----
@pytest.mark.skipif(
    not _IN_USE_AVAILABLE, reason="in-use-block predicate implemented in Plan 04"
)
def test_in_use_block(tmp_path):
    """A voice used by a non-terminal job OR a per-engine default is in-use."""
    db = _make_db(tmp_path)

    # Arm 1: a PENDING (non-terminal) job references the voice.
    create_job(db, Job(
        id="job-pending", filename="a.pdf", file_type="pdf",
        upload_path="/tmp/a.pdf", status=JobStatus.PENDING,
        tts_engine="piper", tts_voice="en_US-amy-medium",
    ))
    assert _call_in_use(db, "piper", "en_US-amy-medium") is True

    # Arm 2: stored as the per-engine default voice (tts.default_voice.<engine>).
    set_setting(db, "tts.default_voice.piper", "en_GB-alan-medium")
    assert _call_in_use(db, "piper", "en_GB-alan-medium") is True

    # Not in use: no job references it and it is no engine's default.
    assert _call_in_use(db, "piper", "en_US-lessac-medium") is False

    # A voice only referenced by a TERMINAL (completed) job is NOT in use.
    create_job(db, Job(
        id="job-done", filename="b.pdf", file_type="pdf",
        upload_path="/tmp/b.pdf", status=JobStatus.COMPLETED,
        tts_engine="piper", tts_voice="en_US-lessac-medium",
    ))
    assert _call_in_use(db, "piper", "en_US-lessac-medium") is False


# --- VOICE-07: an unreferenced voice uninstalls (deletes the pair) -----------
@pytest.mark.skipif(
    not _UNINSTALL_AVAILABLE, reason="uninstall_voice implemented in Plan 04"
)
def test_uninstall_deletes_pair(tmp_path, monkeypatch):
    """Uninstalling an installed voice removes its ``.onnx`` (+ ``.onnx.json``)."""
    monkeypatch.setattr("diana.paths.model_dir", lambda: tmp_path)
    onnx = tmp_path / "en_US-amy-medium.onnx"
    cfg = tmp_path / "en_US-amy-medium.onnx.json"
    onnx.write_bytes(b"fake-model")
    cfg.write_bytes(b"{}")
    # A sibling voice that must survive the targeted delete.
    keep = tmp_path / "en_GB-alan-medium.onnx"
    keep.write_bytes(b"keep-me")

    _uninstall_voice("en_US-amy-medium")

    assert not onnx.exists() and not cfg.exists(), "the .onnx + .onnx.json pair is removed"
    assert keep.exists(), "an unrelated voice file is left intact"


# --- VOICE-07 / D-18: bulk partial cleanup globs only *.part -----------------
@pytest.mark.skipif(
    not _CLEAN_AVAILABLE, reason="bulk partial cleanup implemented in Plan 04"
)
def test_clean_partials(tmp_path, monkeypatch):
    """All ``*.part`` files in model_dir are removed; real files survive (D-18)."""
    monkeypatch.setattr("diana.paths.model_dir", lambda: tmp_path)
    parts = [
        tmp_path / "en_US-amy-medium.onnx.part",
        tmp_path / "kokoro-v1.0.onnx.part",
        tmp_path / "voices-v1.0.bin.part",
    ]
    for p in parts:
        p.write_bytes(b"partial")
    # Real, completed files that must NOT be deleted.
    survivors = [tmp_path / "en_US-lessac-medium.onnx", tmp_path / "voices-v1.0.bin"]
    for s in survivors:
        s.write_bytes(b"complete")

    _clean_partials()

    assert all(not p.exists() for p in parts), "every orphaned .part is cleaned"
    assert all(s.exists() for s in survivors), "non-.part files survive the cleanup"
