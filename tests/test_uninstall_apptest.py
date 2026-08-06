"""Interaction-level AppTest checks for the VOICE-07 / Kokoro-download UI (Plan 04-06).

These drive the REAL Settings ▸ Voices Streamlit flows through
``st.testing.v1.AppTest`` and assert on the resulting widgets/state — not merely that
the page renders. They are the standing post-Phase-4 requirement (shallow "renders
without exception" tests missed real logic bugs at earlier checkpoints), covering:

  * Uninstall confirm flow (D-16): Uninstall an installed Piper voice -> a confirm
    control appears -> Confirm -> the ``.onnx``(+``.onnx.json``) is gone, the voice
    leaves the picker, and the shared voice cache was cleared.
  * In-use block (D-17): a voice that is the per-engine default (or a non-terminal
    job's choice) is BLOCKED with a message and the file remains.
  * Partial cleanup (D-18): with ``.part`` files in a tmp model_dir, a per-item
    "Remove partial" clears one and the bulk "Clean up partial downloads" clears all.
  * Kokoro download row (D-19/D-04): NOT installed -> a download row with the
    >200 MB footprint confirm renders (not the old wget hint); installed -> Ready.

Everything is deterministic and OFFLINE: ``paths.model_dir``/``voices_dir`` are
monkeypatched to ``tmp_path``, the config singleton points at a tmp sqlite DB, and the
voice-cache enumerators are stubbed so no real ``say -v '?'`` shell or network/Kokoro
download runs. No test starts a real download thread.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

import diana.config as C
import diana.dashboard.voice_cache as VC
import diana.paths as P
from diana.database import create_job, init_db, set_setting
from diana.models import Job, JobStatus
from diana.tts.base import TTSVoice

try:
    from streamlit.testing.v1 import AppTest
    _APPTEST = True
except ImportError:  # pragma: no cover - AppTest ships with the pinned Streamlit
    _APPTEST = False

pytestmark = pytest.mark.skipif(not _APPTEST, reason="streamlit AppTest unavailable")

_PAGE = str(
    Path(__file__).resolve().parent.parent
    / "diana" / "dashboard" / "pages" / "5_Settings.py"
)

# The installed Piper voice these tests drive. It MUST be in the bundled CURATED
# subset (the offline default catalog view) so its row — and thus the Uninstall /
# Remove-partial controls — renders without toggling "Show all". ``en_US-lessac-medium``
# is the curated en-us pick.
_VOICE = TTSVoice("en_US-lessac-medium", "Lessac (US Medium)", "en-us", "female", "medium")
_VID = _VOICE.id


def _write_voice(model_dir: Path, voice_id: str) -> tuple[Path, Path]:
    """Lay down an installed Piper voice pair (``.onnx`` + ``.onnx.json``) in tmp."""
    onnx = model_dir / f"{voice_id}.onnx"
    cfg = model_dir / f"{voice_id}.onnx.json"
    onnx.write_bytes(b"fake-model-bytes")
    cfg.write_bytes(b"{}")
    return onnx, cfg


def _run_app(monkeypatch, tmp_path, *, piper_voices=None, all_pairs=None):
    """Build + run the Settings page under AppTest, fully offline/deterministic.

    Points ``model_dir``/``voices_dir`` at ``tmp_path``, the config singleton at a tmp
    DB, stubs the cached voice enumerators (so no OS ``say`` shell / network), and
    replaces ``clear_voice_cache`` with a Mock (the real one calls ``.clear()`` on the
    cache objects we stubbed away). The same tmp DB path is returned so a test can seed
    jobs / default-voice keys against the exact DB the page reads. Returns
    ``(at, db_path, clear_cache_mock)`` with ``at`` already run.
    """
    model_dir = tmp_path / "models"
    model_dir.mkdir(exist_ok=True)
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir(exist_ok=True)
    db_path = str(tmp_path / "diana.db")
    init_db(db_path)

    cfg = C.load_config()
    cfg.storage.database_path = db_path
    # Keep the General tab on native_os so its Default-Voice picker does NOT persist a
    # ``tts.default_voice.piper`` key — otherwise the browsed Piper voice would be
    # auto-set as the piper default and (correctly) blocked from uninstall (D-17),
    # masking the not-in-use confirm path these tests exercise. The Voices-tab catalog
    # browse is independent of ``config.tts.engine``.
    cfg.tts.engine = "native_os"

    pv = list(piper_voices) if piper_voices is not None else [_VOICE]
    pairs = all_pairs if all_pairs is not None else [("piper", v) for v in pv]
    clear_cache_mock = Mock(name="clear_voice_cache")

    monkeypatch.setattr(P, "model_dir", lambda: model_dir)
    monkeypatch.setattr(P, "voices_dir", lambda: voices_dir)
    monkeypatch.setattr(C, "get_config", lambda *a, **k: cfg)
    monkeypatch.setattr(VC, "get_config", lambda *a, **k: cfg)
    monkeypatch.setattr(VC, "cached_voices", lambda engine: list(pv))
    monkeypatch.setattr(VC, "cached_all_engine_voices", lambda: list(pairs))
    # The page does ``from voice_cache import clear_voice_cache``; patching the source
    # attribute before the page execs binds the page name to this Mock.
    monkeypatch.setattr(VC, "clear_voice_cache", clear_cache_mock)

    at = AppTest.from_file(_PAGE, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"
    return at, db_path, clear_cache_mock


def _btn(at, key):
    """The button with the given key, or None if absent this run."""
    for b in at.button:
        if b.key == key:
            return b
    return None


def _has_text(elements, needle):
    """True if any element's value contains ``needle`` (case-insensitive)."""
    needle = needle.lower()
    return any(needle in str(getattr(e, "value", "")).lower() for e in elements)


def _success_containing(at, needle):
    """True if a success message contains ``needle``, tolerating both rerun semantics.

    The freed-space confirmations use the flash pattern: the action stashes its message
    in ``session_state`` and immediately ``st.rerun()``s, so the message renders on the
    NEXT run. AppTest disagrees across versions about whether ``.run()`` follows that
    rerun — streamlit <=1.56 does NOT (the captured tree is the PRE-rerun one, so the
    flash has not been drawn yet), while >=1.61 DOES (the flash is already in the final
    tree). So: check first, and only if the needle is absent, run once more and re-check.
    On 1.61 no extra run happens; on 1.56 the single extra run reveals the flash.

    The check is NEEDLE-based, never emptiness-based: the page renders other
    ``st.success`` badges ("Ready · X MB on disk", "Ready · Kokoro model installed"),
    so ``at.success`` is non-empty even when the flash is absent, and an emptiness gate
    would never trigger the extra run.
    """
    if _has_text(at.success, needle):
        return True
    at.run()
    return _has_text(at.success, needle)


# --- Uninstall confirm flow (D-16) ------------------------------------------
def test_uninstall_confirm_flow_deletes_and_clears_cache(monkeypatch, tmp_path):
    """Uninstall an installed Piper voice: confirm appears -> Confirm -> file gone."""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    onnx, cfg = _write_voice(model_dir, _VID)

    at, _db, clear_cache = _run_app(monkeypatch, tmp_path)

    # Step 1: the installed row exposes an Uninstall control; click it.
    uninstall = _btn(at, f"uninstall_{_VID}")
    assert uninstall is not None, "an installed Piper voice row must offer Uninstall"
    uninstall.click().run()

    # A confirm control now appears (the voice is not in use), with freed-space caption.
    confirm = _btn(at, f"uninstall_yes_{_VID}")
    assert confirm is not None, "clicking Uninstall (not in use) must show a confirm step"
    assert _has_text(at.caption, "cannot be undone"), "confirm step shows the freed-space warning"
    assert onnx.exists(), "nothing is deleted before the user confirms"

    # Step 2: confirm -> the .onnx + .onnx.json are deleted and the cache is cleared.
    confirm.click().run()
    assert not onnx.exists() and not cfg.exists(), "confirm deletes the .onnx + .onnx.json pair"
    assert clear_cache.called, "uninstall must clear the shared voice cache (no-restart refresh)"
    assert _success_containing(at, "uninstalled"), "a success message reports the freed space"


def test_uninstall_cancel_keeps_the_file(monkeypatch, tmp_path):
    """Cancelling the confirm step leaves the installed voice untouched."""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    onnx, _cfg = _write_voice(model_dir, _VID)

    at, _db, _clear = _run_app(monkeypatch, tmp_path)
    _btn(at, f"uninstall_{_VID}").click().run()
    # The confirm step is armed (flag set) after the first Uninstall click.
    _flag = f"_uninstall_confirm_{_VID}"
    assert at.session_state[_flag] is True, "Uninstall (not in use) arms the confirm step"
    cancel = _btn(at, f"uninstall_no_{_VID}")
    assert cancel is not None, "the confirm step offers a Cancel"
    cancel.click().run()

    # Cancel disarms the confirm step (the flag is cleared) and never deletes the voice.
    # (Assert on the session flag, the robust disarm signal — the post-st.rerun() widget
    # snapshot is an AppTest capture artifact, not behavior.)
    assert onnx.exists(), "Cancel must not delete the voice"
    assert _flag not in at.session_state, "Cancel clears the confirm flag (disarms the step)"


# --- In-use block (D-17) ----------------------------------------------------
def test_uninstall_blocked_when_voice_is_engine_default(monkeypatch, tmp_path):
    """A voice set as the per-engine default is blocked from uninstall (file remains)."""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    onnx, _cfg = _write_voice(model_dir, _VID)

    # Seed the per-engine default key BEFORE the app reads it (same tmp DB path).
    db_path = str(tmp_path / "diana.db")
    init_db(db_path)
    set_setting(db_path, "tts.default_voice.piper", _VID)

    at, _db, _clear = _run_app(monkeypatch, tmp_path)
    from diana.database import get_setting
    assert get_setting(_db, "tts.default_voice.piper", None) == _VID

    _btn(at, f"uninstall_{_VID}").click().run()

    # Blocked: a warning is shown, NO confirm control appears, and the file remains.
    assert _btn(at, f"uninstall_yes_{_VID}") is None, "an in-use voice never reaches confirm"
    assert _has_text(at.warning, "switch to another voice first"), "D-17 message is shown"
    assert onnx.exists(), "an in-use voice is not deleted"


def test_uninstall_blocked_when_voice_used_by_pending_job(monkeypatch, tmp_path):
    """A voice referenced by a non-terminal job is blocked from uninstall (D-17)."""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    onnx, _cfg = _write_voice(model_dir, _VID)

    db_path = str(tmp_path / "diana.db")
    init_db(db_path)
    create_job(db_path, Job(
        id="job-pending", filename="a.pdf", file_type="pdf",
        upload_path="/tmp/a.pdf", status=JobStatus.PENDING,
        tts_engine="piper", tts_voice=_VID,
    ))

    at, _db, _clear = _run_app(monkeypatch, tmp_path)
    _btn(at, f"uninstall_{_VID}").click().run()

    assert _btn(at, f"uninstall_yes_{_VID}") is None, "a pending-job voice never reaches confirm"
    assert _has_text(at.warning, "pending or in-progress job"), "D-17 explains the job reference"
    assert onnx.exists(), "a voice a pending job needs is not deleted"


# --- Partial cleanup (D-18) -------------------------------------------------
def test_per_item_remove_partial_clears_one(monkeypatch, tmp_path):
    """A per-item 'Remove partial' removes just that voice's orphaned .part (D-18)."""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    _write_voice(model_dir, _VID)
    part = model_dir / f"{_VID}.onnx.part"
    part.write_bytes(b"partial")
    other_part = model_dir / "kokoro-v1.0.int8.onnx.part"
    other_part.write_bytes(b"partial")

    at, _db, _clear = _run_app(monkeypatch, tmp_path)
    remove = _btn(at, f"rmpart_{_VID}")
    assert remove is not None, "a row with an orphaned .part offers 'Remove partial'"
    remove.click().run()

    assert not part.exists(), "the per-item action removes this voice's .part"
    assert other_part.exists(), "it leaves unrelated .part files alone (bulk handles those)"


def _cancelled_dl_state(total: int = 10) -> dict:
    """A synthesized TERMINAL-cancelled ``dl_state`` record (worker stopped, .part kept).

    Mirrors exactly what the download worker leaves after a Cancel: ``cancel`` True
    (the UI request) AND ``cancelled`` True (the worker's terminal marker), with some
    bytes already streamed. ``_download_action`` maps this to ``"resume"`` — the state
    the human-verify checkpoint exercised. No thread/network: a plain dict the page reads.
    """
    return {
        "downloaded": total // 2, "total": total, "done": False,
        "error": None, "cancel": True, "cancelled": True,
    }


def test_cancelled_row_offers_both_resume_and_remove_partial(monkeypatch, tmp_path):
    """The 04-06 checkpoint bug: after Cancel, a row with a ``.part`` must offer BOTH
    Resume AND Remove partial (the latter was unreachable while ``active`` was True).

    Synthesize the post-Cancel state — a TERMINAL-cancelled ``dl_state`` record plus the
    kept ``.part`` on disk — then assert the row exposes the two distinct controls. This
    is the path the orphan-``.part`` test could never hit (it had NO dl_state record).
    """
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    part = model_dir / f"{_VID}.onnx.part"
    part.write_bytes(b"half-a-model")

    at, _db, _clear = _run_app(monkeypatch, tmp_path)
    # Seed the cancelled record the worker would have left, then re-run the page so the
    # catalog row derives action == "resume" from it (the checkpoint scenario).
    at.session_state["dl_state"] = {_VID: _cancelled_dl_state()}
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    resume = _btn(at, f"resume_{_VID}")
    remove = _btn(at, f"rmpart_{_VID}")
    assert resume is not None, "a cancelled/resumable row must still offer Resume (continue from .part)"
    assert remove is not None, (
        "a cancelled/resumable row with a .part must ALSO offer 'Remove partial' "
        "(the D-18 control was unreachable in this state before the fix)"
    )
    assert resume.key != remove.key, "Resume and Remove partial must be distinct controls"
    assert part.exists(), "merely rendering the row deletes nothing"


def test_cancelled_row_remove_partial_unlinks_and_resets_to_install(monkeypatch, tmp_path):
    """Clicking Remove partial in the cancelled state unlinks the ``.part``, clears the
    ``dl_state`` record, and the row falls back to Install (not stuck on Resume)."""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    part = model_dir / f"{_VID}.onnx.part"
    part.write_bytes(b"half-a-model")

    at, _db, _clear = _run_app(monkeypatch, tmp_path)
    at.session_state["dl_state"] = {_VID: _cancelled_dl_state()}
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    remove = _btn(at, f"rmpart_{_VID}")
    assert remove is not None, "the cancelled row offers 'Remove partial'"
    remove.click().run()

    assert not part.exists(), "Remove partial unlinks this voice's .part"
    # AppTest's session_state is a custom mapping (no ``.get``); index the dl_state dict
    # and assert this voice's record was popped (so the row cannot stay stuck on Resume).
    _dl_state = at.session_state["dl_state"] if "dl_state" in at.session_state else {}
    assert _VID not in _dl_state, (
        "Remove partial clears the dl_state record so the row does not stay stuck on Resume"
    )
    # With the record gone and the .part deleted, the row is back to Install and no longer
    # offers Resume. (Assert on the rebuilt action column — the robust reset signal. The
    # stale ``rmpart`` button lingers in the SAME-run widget snapshot after its handler's
    # st.rerun(); that is an AppTest capture artifact, not behavior — same caveat as
    # ``test_uninstall_cancel_keeps_the_file`` — so we assert the action-column reset,
    # which a clean re-render confirms drops the Remove-partial control too.)
    assert _btn(at, f"install_{_VID}") is not None, "the row resets to the Install state"
    assert _btn(at, f"resume_{_VID}") is None, "no Resume once the partial is discarded"


def test_bulk_clean_up_partials_removes_all(monkeypatch, tmp_path):
    """The bulk 'Clean up partial downloads' clears every orphaned .part (D-18)."""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    parts = [
        model_dir / "en_US-lessac-medium.onnx.part",
        model_dir / "kokoro-v1.0.int8.onnx.part",
        model_dir / "voices-v1.0.bin.part",
    ]
    for p in parts:
        p.write_bytes(b"partial")
    survivor = model_dir / "voices-v1.0.bin"
    survivor.write_bytes(b"complete")

    at, _db, _clear = _run_app(monkeypatch, tmp_path)
    bulk = None
    for b in at.button:
        if b.label == "Clean up partial downloads":
            bulk = b
            break
    assert bulk is not None, "the Voices tab offers a bulk 'Clean up partial downloads'"
    bulk.click().run()

    assert all(not p.exists() for p in parts), "every orphaned .part is removed"
    assert survivor.exists(), "completed files survive the bulk cleanup"
    assert _has_text(at.success, "removed 3 partial"), "the count of removed files is reported"


# --- Kokoro download row (D-19/D-04) ----------------------------------------
def test_kokoro_row_not_installed_shows_download_and_footprint_confirm(monkeypatch, tmp_path):
    """Kokoro NOT installed: a download row renders (not the wget hint), with D-04 confirm."""
    # Empty model_dir -> kokoro_model_installed() is False.
    at, _db, _clear = _run_app(monkeypatch, tmp_path)

    # The engine-level Kokoro row offers a Download model button and a variant picker.
    assert _btn(at, "kokoro_download") is not None or _btn(at, "kokoro_download_confirm") is not None, \
        "a not-installed Kokoro row offers a Download model action"
    assert any(s.key == "_kokoro_variant" for s in at.selectbox), "a model-variant picker renders"
    assert not _has_text(at.caption, "wget"), "the old terminal wget hint is gone"
    assert _has_text(at.caption, "one model"), "the Kokoro row explains it is one model, many voices"

    # Select the large f32 variant -> the D-04 >200 MB footprint confirm appears.
    variant = next(s for s in at.selectbox if s.key == "_kokoro_variant")
    variant.set_value("f32").run()
    assert _has_text(at.warning, "large"), "the >200 MB f32 asset shows a footprint confirm (D-04)"
    assert _btn(at, "kokoro_download_confirm") is not None, "the large download is gated behind a confirm"


def test_kokoro_row_installed_shows_ready(monkeypatch, tmp_path):
    """Kokoro installed: the row shows Ready and offers no download."""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    (model_dir / "kokoro-v1.0.int8.onnx").write_bytes(b"model")
    (model_dir / "voices-v1.0.bin").write_bytes(b"voices")

    at, _db, _clear = _run_app(monkeypatch, tmp_path)
    assert _has_text(at.success, "kokoro model installed"), "an installed Kokoro model reads Ready"
    assert _btn(at, "kokoro_download") is None, "no Download action when already installed"
    assert _btn(at, "kokoro_installed") is not None, "the row shows a disabled Installed marker"
