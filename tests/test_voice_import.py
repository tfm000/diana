"""Wave-0 RED/skip scaffolds for manual-import filename validation (Plan 04).

VOICE-04 lets a user import a Piper ``.onnx`` + ``.onnx.json`` pair via the UI;
HARD-03 requires the import to defend against path traversal / zip-slip. The
validator (``safe_voice_dest``) reuses the exact guard already in
``1_Upload.py:268-284``: ``os.path.basename`` to strip path components, a
resolved-prefix ``startswith(model_dir)`` containment check, plus an
``.onnx``/``.onnx.json`` extension allow-list (RESEARCH Pattern 5).

The symbol lands in Plan 04; its module home is the implementer's choice
(``diana.tts.catalog`` / a UI helper / ``diana.tts.install_state``), so all are
probed. Collection stays GREEN until it lands. Threat T-04-PATH.
"""

import pytest

# --- Guarded probe: the import validator lands in Plan 04 -------------------
_safe_voice_dest = None
for _modname, _attr in (
    ("diana.tts.catalog", "safe_voice_dest"),
    ("diana.tts.install_state", "safe_voice_dest"),
    ("diana.dashboard.voice_import", "safe_voice_dest"),
    ("diana.tts.voice_import", "safe_voice_dest"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _safe_voice_dest = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue
_VALIDATOR_AVAILABLE = _safe_voice_dest is not None


@pytest.mark.skipif(
    not _VALIDATOR_AVAILABLE, reason="safe_voice_dest validator implemented in Plan 04"
)
def test_safe_dest(tmp_path, monkeypatch):
    """A clean name lands in ``model_dir``; traversal is contained; bad ext rejected."""
    monkeypatch.setattr("diana.paths.model_dir", lambda: tmp_path)
    model_dir = tmp_path

    # 1. A plain, well-formed Piper voice name resolves directly under model_dir.
    dest = _safe_voice_dest("en_US-amy-medium.onnx")
    assert dest.name == "en_US-amy-medium.onnx"
    assert dest.parent.resolve() == model_dir.resolve()
    # Resolved-prefix containment (the HARD-03 invariant): the dest never escapes.
    assert str(dest.resolve()).startswith(str(model_dir.resolve()))

    # The sibling config file is equally accepted (the import is a pair).
    cfg = _safe_voice_dest("en_US-amy-medium.onnx.json")
    assert cfg.name == "en_US-amy-medium.onnx.json"
    assert str(cfg.resolve()).startswith(str(model_dir.resolve()))

    # 2. A traversal attempt must NOT escape model_dir. The basename guard
    #    strips the ``../`` components; an implementation may instead raise.
    #    Either way the result must never resolve outside the cache dir.
    try:
        traversed = _safe_voice_dest("../../etc/evil.onnx")
    except ValueError:
        pass  # rejecting outright is an acceptable, stricter behavior
    else:
        assert str(traversed.resolve()).startswith(str(model_dir.resolve())), (
            "a traversal name must be contained within model_dir, never escape it"
        )
        assert ".." not in traversed.parts

    # 3. An absolute path likewise must not escape model_dir.
    try:
        absolute = _safe_voice_dest("/etc/passwd.onnx")
    except ValueError:
        pass
    else:
        assert str(absolute.resolve()).startswith(str(model_dir.resolve()))

    # 4. A non-.onnx / non-.onnx.json extension is rejected (extension allow-list).
    with pytest.raises(ValueError):
        _safe_voice_dest("evil.txt")
    with pytest.raises(ValueError):
        _safe_voice_dest("payload.sh")
