"""Wave-0 RED/skip scaffold for the bundled-``uv`` provisioner (Plan 03).

HEAVY-01/02/03 install heavy Python deps into an isolated per-engine venv with NO
terminal and NO system Python — driven by a bundled ``uv`` binary over
``subprocess`` (RESEARCH Pattern 1, the load-bearing D-05/D-06 mechanism). These
tests MOCK every subprocess (uv never really runs) and assert the contract:

  - ``provision_venv`` builds the correct ``uv`` argv in the correct ORDER:
    ``uv venv --python <py> <venv>`` BEFORE ``uv pip install --python <venv-python>
    <pkgs> [--extra-index-url ...]`` — and uses ``paths.uv_binary()``, never a bare
    ``uv`` from PATH (Pitfall 1 / frozen-app safety).
  - two-phase progress: Phase-A uv stdout lines stream into an ``on_line`` hook
    (Pattern 3) so the UI ``dl_state`` can render the current step.
  - ``install_engine`` runs ``has_space`` BEFORE any byte (D-04/D-05) and writes
    the ``.{engine}.installed`` marker only on success.

The symbols land in Wave 3; module home is the implementer's choice
(``diana.tts.heavy_install`` OR folded into ``diana.tts.install_state``), so each
is probed in both homes. Collection stays GREEN until they land, then these flip
to live gates with zero edits.
"""

import inspect
import sys

import pytest

# --- Guarded probes: the provisioner lands in Wave 3 ------------------------
_provision_venv = None
_install_engine = None
for _modname in ("diana.tts.heavy_install", "diana.tts.install_state"):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=["provision_venv"])
    except ImportError:
        continue
    if _provision_venv is None and hasattr(_mod, "provision_venv"):
        _provision_venv = _mod.provision_venv
    if _install_engine is None and hasattr(_mod, "install_engine"):
        _install_engine = _mod.install_engine
_PROVISION_AVAILABLE = _provision_venv is not None
_INSTALL_AVAILABLE = _install_engine is not None


def _fake_uv(tmp_path):
    """A placeholder bundled-uv binary path (never executed — subprocess mocked)."""
    uv = tmp_path / "bin" / ("uv.exe" if sys.platform == "win32" else "uv")
    uv.parent.mkdir(parents=True, exist_ok=True)
    uv.write_text("#!bundled uv placeholder\n", encoding="utf-8")
    return uv


def _bind_uv(monkeypatch, uv_path):
    """Point ``paths.uv_binary()`` at the placeholder (raising=False until it lands)."""
    from diana import paths

    monkeypatch.setattr(paths, "uv_binary", lambda: uv_path, raising=False)


def _patch_has_space(monkeypatch, retval):
    """Force ``downloader.has_space`` (+ any heavy_install re-export) to ``retval``."""
    import diana.downloads.downloader as _dl

    monkeypatch.setattr(_dl, "has_space", lambda *a, **k: retval)
    hi = sys.modules.get("diana.tts.heavy_install")
    if hi is not None and hasattr(hi, "has_space"):
        monkeypatch.setattr(hi, "has_space", lambda *a, **k: retval, raising=False)


def _call_install(fn, engine):
    """Call ``install_engine(engine, ...)`` tolerant of optional progress hooks."""
    sig = inspect.signature(fn)
    kwargs = {}
    for hook in ("on_line", "progress"):
        if hook in sig.parameters:
            kwargs[hook] = lambda *a, **k: None
    if "state" in sig.parameters:
        kwargs["state"] = {}
    return fn(engine, **kwargs)


# --- D-05/D-06: provision_venv builds the correct uv argv, in order ---------
@pytest.mark.skipif(
    not _PROVISION_AVAILABLE,
    reason="provision_venv (uv provisioner) lands in Wave 3",
)
def test_provision_venv_uv_argv_and_order(tmp_path, tmp_data_paths, mock_uv,
                                          monkeypatch):
    """`uv venv ...` precedes `uv pip install ...`; both use paths.uv_binary()."""
    uv = _fake_uv(tmp_path)
    _bind_uv(monkeypatch, uv)

    venv_path = tmp_data_paths["venvs_dir"] / "orpheus"
    _provision_venv(venv_path, ["orpheus-cpp"])

    # mock_uv recorded each uv invocation's argv (Popen + run).
    venv_idx = next(i for i, c in enumerate(mock_uv) if "venv" in c)
    install_idx = next(i for i, c in enumerate(mock_uv) if "install" in c)
    assert venv_idx < install_idx, "the venv must exist before packages install"

    venv_call = mock_uv[venv_idx]
    install_call = mock_uv[install_idx]
    # Bundled uv binary — NEVER a bare 'uv' resolved from PATH (frozen-app safety).
    assert venv_call[0] == str(uv)
    assert install_call[0] == str(uv)
    # uv venv --python <py> <venv>
    assert "--python" in venv_call
    assert str(venv_path) in [str(x) for x in venv_call]
    # Idempotent re-install / shared-venv reuse: --allow-existing so a retry after a
    # failed attempt reuses the partial venv and the shared torch venv (F5+Fish) is
    # reused rather than erroring "venv already exists" (regression guard).
    assert "--allow-existing" in venv_call, (
        "uv venv must pass --allow-existing (idempotent re-install + shared-venv reuse)"
    )
    # uv pip install --python <venv-python> orpheus-cpp
    assert "pip" in install_call and "install" in install_call
    assert "--python" in install_call
    assert any(
        str(x).endswith(("bin/python", "Scripts/python.exe"))
        for x in install_call
    ), "install must target the venv's own python (ABI pinned, not the app)"
    assert "orpheus-cpp" in install_call


# --- Pitfall 2: the abetlen wheel index is passed through -------------------
@pytest.mark.skipif(
    not _PROVISION_AVAILABLE,
    reason="provision_venv (uv provisioner) lands in Wave 3",
)
def test_provision_venv_extra_index_passthrough(tmp_path, tmp_data_paths, mock_uv,
                                               monkeypatch):
    """An ``extra_index`` (the llama-cpp wheel index) reaches the install argv."""
    uv = _fake_uv(tmp_path)
    _bind_uv(monkeypatch, uv)
    idx_url = "https://abetlen.github.io/llama-cpp-python/whl/cpu"

    sig = inspect.signature(_provision_venv)
    kw = {}
    if "extra_index" in sig.parameters:
        kw["extra_index"] = idx_url
    elif "extra_index_url" in sig.parameters:
        kw["extra_index_url"] = idx_url
    else:  # the provisioner exposes the index a different way
        pytest.skip("provision_venv passes the wheel index via a different param")

    _provision_venv(tmp_data_paths["venvs_dir"] / "orpheus",
                    ["llama-cpp-python"], **kw)

    install_call = next(c for c in mock_uv if "install" in c)
    assert "--extra-index-url" in install_call
    assert idx_url in install_call


# --- Pattern 3: Phase-A progress streams uv stdout into the on_line hook -----
@pytest.mark.skipif(
    not _PROVISION_AVAILABLE,
    reason="provision_venv (uv provisioner) lands in Wave 3",
)
def test_provision_venv_streams_progress(tmp_path, tmp_data_paths, mock_uv,
                                        monkeypatch):
    """uv stdout lines are streamed into the progress callback (dl_state['step'])."""
    uv = _fake_uv(tmp_path)
    _bind_uv(monkeypatch, uv)

    if "on_line" not in inspect.signature(_provision_venv).parameters:
        pytest.skip("provision_venv reports progress via a different hook")

    seen: list[str] = []
    _provision_venv(tmp_data_paths["venvs_dir"] / "orpheus", ["orpheus-cpp"],
                    on_line=seen.append)
    # The fake Popen (mock_uv) streams "Resolved..."/"Installed..." stdout lines.
    assert any("Installed" in s or "Resolved" in s for s in seen)


# --- D-04/D-05: install_engine pre-checks disk BEFORE any byte --------------
@pytest.mark.skipif(
    not _INSTALL_AVAILABLE,
    reason="install_engine (two-phase install) lands in Wave 3",
)
def test_install_engine_disk_precheck_blocks(tmp_path, tmp_data_paths, mock_uv,
                                            monkeypatch):
    """When has_space is False, NO uv runs and NO marker is written (D-04/D-05)."""
    _bind_uv(monkeypatch, _fake_uv(tmp_path))
    _patch_has_space(monkeypatch, (False, 0))
    marker = tmp_data_paths["venvs_dir"] / ".orpheus.installed"

    try:
        _call_install(_install_engine, "orpheus")
    except Exception:
        pass  # refusal may surface as an exception OR a falsy return — both OK

    assert not marker.exists(), "no .installed marker when the disk pre-check fails"
    assert mock_uv == [], "has_space must gate BEFORE any uv subprocess (D-04/D-05)"


# --- install_engine writes the .installed marker only on success -------------
@pytest.mark.skipif(
    not _INSTALL_AVAILABLE,
    reason="install_engine (two-phase install) lands in Wave 3",
)
def test_install_engine_marks_installed_on_success(tmp_path, tmp_data_paths,
                                                  mock_uv, monkeypatch):
    """A successful install lands the ``.{engine}.installed`` marker probes look for."""
    _bind_uv(monkeypatch, _fake_uv(tmp_path))
    _patch_has_space(monkeypatch, (True, 10 ** 12))

    _call_install(_install_engine, "orpheus")

    assert (tmp_data_paths["venvs_dir"] / ".orpheus.installed").exists()
