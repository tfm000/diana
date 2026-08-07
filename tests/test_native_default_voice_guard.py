"""AppTest regressions: a raising native_os default-voice probe must not kill a page.

These pin DEGRADATION, not correctness. The CORRECTNESS gate for the WinRT member
spellings lives in ``tests/test_native_os_engine.py`` (real, non-MagicMock fakes that
raise AttributeError on the wrong spelling) — the page guard here does NOT make that
test redundant, and must never be treated as a substitute for it.

Context: the first-ever Windows CI run (quick-260807-3yx) failed 39 tests per job. Only
TWO of those were the actual bug — the win32 branch read two static members that do not
exist. But because both ``5_Settings.py`` and ``1_Upload.py`` call
``_engine_default_voice`` at PAGE MODULE LEVEL, that single AttributeError took down the
entire page, and ~32 unrelated Settings/Upload AppTests failed with it. One engine's
probe blowing up must never cascade like that again.

There is no Windows box available, so the win32 AttributeError is reproduced on macOS by
forcing ``NativeOSEngine.default_voice`` to raise ``RuntimeError`` — the page-level effect
is identical (an unguarded exception escaping the module-level probe).

Everything is deterministic + OFFLINE: per-user dirs point at ``tmp_path``, the config
singleton points at a tmp sqlite DB, and the cached voice enumerators are stubbed, so no
real ``say`` shell / network / model work runs.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

import diana.config as C
import diana.dashboard.voice_cache as VC
import diana.paths as P
from diana.database import init_db
from diana.tts.base import TTSVoice
from diana.tts.native_os_engine import NativeOSEngine

try:
    from streamlit.testing.v1 import AppTest
    _APPTEST = True
except ImportError:  # pragma: no cover - AppTest ships with the pinned Streamlit
    _APPTEST = False

pytestmark = pytest.mark.skipif(not _APPTEST, reason="streamlit AppTest unavailable")

_PAGES = Path(__file__).resolve().parent.parent / "diana" / "dashboard" / "pages"
_UPLOAD = str(_PAGES / "1_Upload.py")
_SETTINGS = str(_PAGES / "5_Settings.py")


def _raising_default_voice(self, *a, **k):
    """macOS stand-in for the win32 AttributeError the first Windows CI run hit."""
    raise RuntimeError("simulated WinRT probe failure (quick-260807-3yx)")


def _offline_env(monkeypatch, tmp_path):
    """Tmp dirs + tmp-DB config singleton + stubbed enumerators (no shell/network)."""
    for name in ("venvs_dir", "hf_cache_dir", "model_dir", "voices_dir"):
        sub = tmp_path / name.replace("_dir", "")
        sub.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(P, name, lambda _d=sub: _d, raising=False)

    db_path = str(tmp_path / "diana.db")
    init_db(db_path)
    cfg = C.load_config()
    cfg.storage.database_path = db_path
    cfg.tts.engine = "native_os"
    monkeypatch.setattr(C, "get_config", lambda *a, **k: cfg)
    monkeypatch.setattr(VC, "get_config", lambda *a, **k: cfg)

    # A tiny deterministic native_os list: the picker still has options, so the ONLY
    # thing failing in these runs is the default-voice probe itself.
    nat = [TTSVoice("nat-0", "Native 0", "en-us", "male")]
    monkeypatch.setattr(VC, "cached_voices", lambda engine_name: list(nat))
    monkeypatch.setattr(VC, "cached_all_engine_voices", lambda: [("native_os", nat[0])])
    monkeypatch.setattr(VC, "clear_voice_cache", Mock(name="clear_voice_cache"))

    # The regression trigger.
    monkeypatch.setattr(NativeOSEngine, "default_voice", _raising_default_voice)
    return cfg, db_path


def test_settings_renders_when_default_voice_probe_raises(monkeypatch, tmp_path):
    """Settings still renders when the native_os default-voice probe raises."""
    _offline_env(monkeypatch, tmp_path)

    at = AppTest.from_file(_SETTINGS, default_timeout=30)
    at.run()

    assert at.exception is None or len(at.exception) == 0, (
        f"Settings died on a raising default-voice probe: {at.exception}"
    )


def test_upload_renders_when_default_voice_probe_raises(monkeypatch, tmp_path):
    """Upload still renders when the native_os default-voice probe raises."""
    _offline_env(monkeypatch, tmp_path)

    at = AppTest.from_file(_UPLOAD, default_timeout=30)
    at.run()

    assert at.exception is None or len(at.exception) == 0, (
        f"Upload died on a raising default-voice probe: {at.exception}"
    )
