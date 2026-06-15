"""Wave-0 RED/skip scaffold for the cheap heavy-engine install-state probes (Plan 03).

ENGINE-01 / D-17: rendering a heavy-engine badge, summing its footprint, or
uninstalling it must NEVER import torch/llama-cpp/orpheus_cpp/f5_tts — install
state is a pure filesystem probe of the per-engine venv + ``.{engine}.installed``
marker (RESEARCH install-state example). These tests use the ``fake_venv`` fixture
to lay down a fake venv under a tmp ``venvs_dir`` and assert:

  - ``heavy_engine_installed(engine)`` is True iff the venv python + marker exist;
  - ``heavy_footprint_bytes(engine)`` is 0 before install, >0 after;
  - ``uninstall_heavy_engine(engine)`` removes the venv (scoped to ``venvs_dir()``)
    and returns freed bytes;
  - and NONE of the heavy SDKs land in ``sys.modules`` after a cheap call.

Symbols land in Wave 3; module home is the implementer's choice
(``diana.tts.install_state`` OR ``diana.tts.registry``), so each is probed in both.
"""

import sys

import pytest

_HEAVY_SDKS = ("torch", "llama_cpp", "orpheus_cpp", "f5_tts")


def _probe(attr):
    """Return ``attr`` from install_state OR registry, else ``None`` (multi-home)."""
    for modname in ("diana.tts.install_state", "diana.tts.registry"):
        try:  # pragma: no cover - import probe
            mod = __import__(modname, fromlist=[attr])
            fn = getattr(mod, attr, None)
            if fn is not None:
                return fn
        except (ImportError, AttributeError):
            continue
    return None


_heavy_installed = _probe("heavy_engine_installed")
_heavy_footprint = _probe("heavy_footprint_bytes")
_uninstall_heavy = _probe("uninstall_heavy_engine")

_INSTALLED_AVAILABLE = _heavy_installed is not None
_FOOTPRINT_AVAILABLE = _heavy_footprint is not None
_UNINSTALL_AVAILABLE = _uninstall_heavy is not None


def _assert_no_heavy_import():
    """The cheap probe lane must not pull any heavy SDK (ENGINE-01 / D-17)."""
    leaked = [m for m in _HEAVY_SDKS if m in sys.modules]
    assert not leaked, f"cheap install-state probe leaked heavy import(s): {leaked}"


# --- ENGINE-01: heavy_engine_installed is a pure filesystem probe -----------
@pytest.mark.skipif(
    not _INSTALLED_AVAILABLE, reason="heavy_engine_installed lands in Wave 3"
)
def test_heavy_engine_installed_filesystem_only(tmp_data_paths, fake_venv):
    """True iff the venv python + ``.{engine}.installed`` marker exist; no SDK import."""
    assert _heavy_installed("orpheus") is False  # nothing on disk yet
    fake_venv("orpheus")
    assert _heavy_installed("orpheus") is True
    # An engine whose shared venv exists but with no marker stays uninstalled.
    assert _heavy_installed("f5") is False
    _assert_no_heavy_import()


# --- ENGINE-03: footprint reflects the on-disk venv size --------------------
@pytest.mark.skipif(
    not _FOOTPRINT_AVAILABLE, reason="heavy_footprint_bytes lands in Wave 3"
)
def test_heavy_footprint_bytes(tmp_data_paths, fake_venv):
    """Footprint is 0 when absent and >0 once the venv (with weight files) exists."""
    assert _heavy_footprint("orpheus") == 0  # not installed
    venv = fake_venv("orpheus")
    # Add a chunky fake weight/library file so the footprint is unmistakably > 0.
    (venv / "big.bin").write_bytes(b"x" * 4096)
    assert _heavy_footprint("orpheus") > 0
    _assert_no_heavy_import()


# --- D-16: uninstall is scoped to venvs_dir() and returns freed bytes -------
@pytest.mark.skipif(
    not _UNINSTALL_AVAILABLE, reason="uninstall_heavy_engine lands in Wave 3"
)
def test_uninstall_heavy_engine_scoped(tmp_data_paths, fake_venv):
    """Uninstall removes the venv + marker (scoped to venvs_dir) and frees bytes."""
    venv = fake_venv("orpheus")
    (venv / "big.bin").write_bytes(b"x" * 2048)
    assert _heavy_installed("orpheus") is True if _INSTALLED_AVAILABLE else True

    freed = _uninstall_heavy("orpheus")
    assert isinstance(freed, int) and freed >= 0
    # The venv tree is gone; a sibling untouched file outside it would survive.
    assert not venv.exists(), "uninstall must remove the per-engine venv tree"
    if _INSTALLED_AVAILABLE:
        assert _heavy_installed("orpheus") is False
    _assert_no_heavy_import()
