"""Bundled-``uv`` provisioner for the heavy opt-in engines (Phase 5, D-05/D-06).

Phase 4 only *downloaded files*; this module *provisions a Python environment*.
The single load-bearing mechanism (RESEARCH Pattern 1 + 3): drive a bundled ``uv``
standalone binary over ``subprocess`` to (Phase A) create a per-engine venv with a
pinned standalone CPython 3.12 and ``uv pip install`` the heavy deps, then (Phase B)
prefetch the model weights via the venv's OWN Python with ``HF_HOME`` pointed at the
per-user cache — streaming two-phase progress into the shared ``dl_state`` dict that
the Settings ``@st.fragment`` poller renders.

Two disciplines are mirrored verbatim from the proven Phase-4 machinery:

  1. **No heavy/Streamlit import at module top.** ``torch`` / ``llama-cpp`` /
     ``orpheus_cpp`` / ``f5_tts`` live ONLY inside the venv, reached by subprocess —
     never the app interpreter (ENGINE-01/D-17). ``streamlit`` is never imported;
     the install thread writes ONLY the shared ``state`` dict (T-05-SRC / Pitfall 6).
     ``paths`` / ``downloader`` / ``database`` are imported lazily inside functions.
  2. **List-argv subprocess, ``shell=False``.** Package names / paths are code-pinned
     (Task-1-verified), never user input; text is never interpolated into a shell
     string (T-05-CMD, the ``native_os_engine`` precedent).

A ``has_space`` disk pre-check gates every install before a single byte is written
(D-04/D-05); the ``uv`` binary is resolved from the bundled path (``paths.uv_binary``),
never a bare ``uv`` from PATH except an explicit dev fallback (T-05-EXE). On success a
``.{engine}.installed`` marker is written under ``venvs_dir()`` — exactly what
``install_state.heavy_engine_installed`` probes.

Confirmed plan-time pins (Task 1, re-verified 2026-06-15) live in ``_BUILTIN_SPECS``;
the engine slices (05-04/05/07) consume them verbatim.
"""

import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# --- Confirmed plan-time pins (Task 1) -------------------------------------
# llama-cpp-python ships ABI-agnostic ``py3-none-<platform>`` wheels on the abetlen
# index for macosx_11_0_arm64 (cpu+metal) AND win_amd64 (cpu) — so a single pin works
# on every supported CPython 3.x with NO source build (Pitfall 2 cleared). macOS uses
# the metal index for GPU; the engine slices select per-OS at install time.
_ABETLEN_CPU = "https://abetlen.github.io/llama-cpp-python/whl/cpu"
_ABETLEN_METAL = "https://abetlen.github.io/llama-cpp-python/whl/metal"


@dataclass
class HeavyInstallSpec:
    """A single heavy engine's install recipe (deps + weights), code-pinned.

    ``packages`` are exact-version pins installed ONLY from PyPI + the abetlen wheel
    index (``extra_index``); ``prefetch_argv`` is the venv-python worker command that
    pulls the weights into the per-user HF cache (Phase B). ``deps_bytes`` /
    ``weights_bytes`` feed the D-04 itemized footprint + the ``has_space`` pre-check.
    """

    engine: str
    venv_name: str
    packages: list[str]
    extra_index: str | None = None
    prefetch_argv: list[str] = field(default_factory=list)
    deps_bytes: int = 0
    weights_bytes: int = 0


# Built-in specs the Settings rows + tests resolve by engine name. Orpheus is
# torch-free in its own venv; F5 + Fish share the 'torch' venv (D-03 shared-torch).
# Footprints are conservative estimates; the Settings row reads exact sizes live (D-04).
_GB = 1024 ** 3
_BUILTIN_SPECS: dict[str, HeavyInstallSpec] = {
    "orpheus": HeavyInstallSpec(
        engine="orpheus",
        venv_name="orpheus",
        packages=["orpheus-cpp==0.0.3", "llama-cpp-python==0.3.29"],
        extra_index=_ABETLEN_CPU,
        prefetch_argv=["-m", "orpheus_cpp", "--prefetch"],
        deps_bytes=int(0.4 * _GB),
        weights_bytes=int(2.6 * _GB),
    ),
    "f5": HeavyInstallSpec(
        engine="f5",
        venv_name="torch",
        packages=["f5-tts==1.1.20"],
        extra_index=None,
        prefetch_argv=["-m", "f5_tts", "--prefetch"],
        deps_bytes=int(3.0 * _GB),
        weights_bytes=int(1.4 * _GB),
    ),
    "fish": HeavyInstallSpec(
        engine="fish",
        venv_name="torch",
        packages=[
            "fish-speech @ git+https://github.com/fishaudio/fish-speech"
            "@e5e292632cb11e7a27b2b7487f58f612bc101e13",
        ],
        extra_index=None,
        # Populated below after the dict is constructed (WR-04): fish-speech ships no
        # __main__ that accepts --prefetch, so the correct form is the bundled
        # fish_worker.py script, matching fish_install_spec() in fish_engine.py.
        prefetch_argv=[],
        deps_bytes=int(3.0 * _GB),
        weights_bytes=int(4.0 * _GB),
    ),
}

# WR-04: fill in the fish prefetch_argv now that paths is importable.  The form
# must be the bundled worker-script path + --prefetch (same as fish_install_spec()
# in fish_engine.py), NOT "-m fish_speech" which assumes a __main__ fish-speech
# never ships. Populated post-dict so paths is imported lazily (D-17).
def _init_fish_prefetch_argv() -> None:
    from diana import paths as _paths

    _BUILTIN_SPECS["fish"].prefetch_argv = [
        str(_paths.heavy_worker("fish_worker.py")), "--prefetch",
    ]


_init_fish_prefetch_argv()


def _is_win() -> bool:
    return sys.platform == "win32"


def _venv_python(venv_path: Path) -> Path:
    """The interpreter path inside a venv, per OS (matches the install-state probe)."""
    return venv_path / ("Scripts/python.exe" if _is_win() else "bin/python")


def _resolve_uv() -> str:
    """The bundled ``uv`` binary, or a PATH fallback ONLY in dev (T-05-EXE).

    Production bundles the signed ``uv`` under ``diana/data/bin/`` (Phase 6), so the
    fallback never fires in a shipped app. The dev fallback lets the provisioner run
    from a source checkout before the binary is bundled.
    """
    from diana import paths

    uv = paths.uv_binary()
    if uv.exists():
        return str(uv)
    import shutil

    found = shutil.which("uv")
    if found:
        logger.warning("bundled uv missing at %s; falling back to PATH uv (dev only)", uv)
        return found
    raise FileNotFoundError(
        f"uv binary not found (bundled: {uv}); cannot provision a heavy-engine venv"
    )


def _run(cmd: list[str], on_line=None, cancel=None, timeout: int = 3600) -> None:
    """Run a list-argv command, streaming each stdout line to ``on_line``.

    ``shell=False`` (list argv) — package/path values are code-pinned, never a shell
    string (T-05-CMD). Phase-A ``uv`` output has no clean byte totals, so each stdout
    line is forwarded as a step label (Pattern 3); a non-zero exit raises RuntimeError.

    ``cancel``: optional callable; when truthy, the child process is terminated
    immediately and ``RuntimeError("install cancelled by user")`` is raised so the
    caller can set ``state["cancelled"]`` (WR-01 cancel-during-Phase-A fix).

    ``timeout``: wall-clock deadline in seconds (default 3600 — generous for multi-GB
    installs, matching Phase B's limit). Exceeded deadline terminates the child and
    raises ``RuntimeError`` so a stalled ``uv`` command cannot block the thread forever
    (WR-02 timeout fix).

    The last 20 lines of combined stdout/stderr are captured and included in the
    ``RuntimeError`` message on non-zero exit so install failures are diagnosable
    without log spelunking (WR-03 error-text fix).
    """
    import time
    from collections import deque

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    deadline = time.monotonic() + timeout
    tail: deque[str] = deque(maxlen=20)
    try:
        if proc.stdout is not None:
            for line in proc.stdout:
                # WR-01: poll cancel flag between lines; terminate child on cancel.
                if cancel and cancel():
                    proc.terminate()
                    proc.wait()
                    raise RuntimeError("install cancelled by user")
                # WR-02: enforce wall-clock deadline between lines.
                if time.monotonic() > deadline:
                    proc.terminate()
                    proc.wait()
                    raise RuntimeError(
                        f"install step timed out after {timeout}s: {' '.join(cmd[:2])}"
                    )
                line = line.rstrip()
                tail.append(line)  # WR-03: retain for error context
                if on_line and line:
                    on_line(line)
    except RuntimeError:
        raise
    except Exception:
        proc.terminate()
        proc.wait()
        raise
    # WR-03: include captured output in the failure message so the error is diagnosable.
    if proc.wait() != 0:
        detail = "\n".join(tail) or "(no output)"
        raise RuntimeError(
            f"install step failed: {' '.join(cmd[:2])}\n{detail}"
        )


def provision_venv(venv_path, packages, extra_index=None, py="3.12",
                   on_line=None, cancel=None, timeout: int = 3600) -> Path:
    """Create an isolated venv via bundled ``uv`` and pip-install ``packages``.

    RESEARCH Pattern 1 — the D-05/D-06 mechanism. ``uv venv --python <py> <venv>``
    creates the venv with a managed standalone CPython (uv downloads it if absent),
    THEN ``uv pip install --python <venv-python> <packages> [--extra-index-url ...]``
    installs into THAT venv (ABI pinned to the venv's python, not the frozen app).
    Returns the venv's python path. ``on_line`` receives each ``uv`` stdout line so
    the UI ``dl_state['step']`` can render the current step (Phase-A progress).
    ``cancel`` and ``timeout`` are forwarded to ``_run`` (WR-01/WR-02).
    """
    venv_path = Path(venv_path)
    uv = _resolve_uv()
    # 1) create the venv (with a managed standalone CPython at the pinned version).
    _run([uv, "venv", "--python", py, str(venv_path)], on_line, cancel=cancel,
         timeout=timeout)
    vpy = _venv_python(venv_path)
    # 2) install into THAT venv's python (ABI-pinned), optionally via a wheel index.
    cmd = [uv, "pip", "install", "--python", str(vpy), *packages]
    if extra_index:
        cmd += ["--extra-index-url", extra_index]
    _run(cmd, on_line, cancel=cancel, timeout=timeout)
    return vpy


def _resolve_spec(spec_or_engine) -> HeavyInstallSpec:
    """Accept either a ``HeavyInstallSpec`` or a built-in engine name."""
    if isinstance(spec_or_engine, HeavyInstallSpec):
        return spec_or_engine
    try:
        return _BUILTIN_SPECS[spec_or_engine]
    except KeyError:
        raise ValueError(f"unknown heavy engine: {spec_or_engine!r}") from None


def install_engine(spec_or_engine, state=None, *, on_line=None, cancel=None) -> None:
    """Two-phase install (deps -> weights) for one heavy engine — the thread target.

    CRITICAL (T-05-SRC / Pitfall 6): runs on a UI background thread and MUST NOT call
    ``st.*``; it writes ONLY the shared ``state`` dict (the ``_download_piper_voice``
    discipline). Any exception lands in ``state['error']`` — it never raises off the
    thread. Steps:

      0. ``has_space(venvs_dir(), deps + weights)`` BEFORE any byte (D-04/D-05) —
         on failure set a clear "need X, only Y free" ``state['error']`` and return.
      A. Phase deps: ``provision_venv(...)`` streaming uv lines into ``state['step']``.
      B. Phase weights: run ``[vpy, *prefetch_argv]`` with ``HF_HOME`` pointed at the
         per-user cache (D-07/Pitfall 8), updating ``state['step']``.
      C. Write the ``.{engine}.installed`` marker and set ``state['done'] = True``.

    A truthy ``cancel()`` or ``state['cancel']`` between phases stops cleanly and sets
    the TERMINAL ``state['cancelled']`` marker (the Phase-4 cancel/resume contract).
    """
    if state is None:
        state = {}
    spec = _resolve_spec(spec_or_engine)

    def _cancelled() -> bool:
        return bool((cancel and cancel()) or state.get("cancel"))

    try:
        from diana import paths
        from diana.downloads import downloader

        venvs = paths.venvs_dir()
        needed = spec.deps_bytes + spec.weights_bytes

        # 0. Disk pre-check BEFORE any byte (D-04/D-05). has_space ancestor-walks a
        #    not-yet-created dir, so it works on a fresh venvs_dir().
        ok, free = downloader.has_space(venvs, needed)
        if not ok:
            state["error"] = (
                f"Not enough disk space: need ~{needed // (1024 ** 2)} MB, "
                f"only ~{free // (1024 ** 2)} MB free."
            )
            return

        def _step(line: str) -> None:
            state["step"] = line
            if on_line:
                on_line(line)

        if _cancelled():
            state["cancelled"] = True
            return

        # A. Phase deps — provision the isolated venv + pip-install heavy packages.
        # Pass _cancelled so _run() can terminate the uv subprocess mid-stream when
        # the user clicks Cancel (WR-01: cancel now interrupts Phase A, not just the
        # between-phase poll below).
        state["phase"] = "deps"
        state["step"] = "Creating environment…"
        vpy = provision_venv(
            venvs / spec.venv_name, spec.packages, spec.extra_index, on_line=_step,
            cancel=_cancelled,
        )

        if _cancelled():
            state["cancelled"] = True
            return

        # B. Phase weights — prefetch model weights via the venv's OWN python with
        #    HF_HOME pointed at the per-user cache (weights never land in ~/.cache).
        state["phase"] = "weights"
        state["step"] = "Downloading model weights…"
        if spec.prefetch_argv:
            env = {**os.environ, "HF_HOME": str(paths.hf_cache_dir())}
            proc = subprocess.run(
                [str(vpy), *spec.prefetch_argv],
                env=env, capture_output=True, text=True, timeout=3600,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"weight prefetch failed: {(proc.stderr or '').strip()[:500]}"
                )

        if _cancelled():
            state["cancelled"] = True
            return

        # C. Success — drop the marker install_state.heavy_engine_installed probes.
        venvs.mkdir(parents=True, exist_ok=True)
        (venvs / f".{spec.engine}.installed").write_text("1", encoding="utf-8")
        state["done"] = True
    except RuntimeError as e:  # noqa: BLE001 — surface to the UI, NEVER st.* on this thread
        # Distinguish a user-initiated cancel (WR-01) from a real install failure so
        # the UI shows the correct terminal state.
        if str(e) == "install cancelled by user":
            state["cancelled"] = True
        else:
            state["error"] = str(e)
    except Exception as e:  # noqa: BLE001
        state["error"] = str(e)


# --- Accept-once NC-license gate (D-08) ------------------------------------
# F5 + Fish weights are non-commercial; the Settings row consults these BEFORE any
# download and persists acceptance so a re-install never re-prompts (survives restart
# via a fresh DB connection). DB import is lazy to keep the module import-light.

def license_accepted(db_path, engine) -> bool:
    """True iff the user has accepted ``engine``'s license (persisted in app_settings)."""
    from diana.database import get_setting

    return get_setting(db_path, f"license.accepted.{engine}", None) == "1"


def accept_license(db_path, engine) -> None:
    """Persist acceptance of ``engine``'s NC license (idempotent; survives restart)."""
    from diana.database import set_setting

    set_setting(db_path, f"license.accepted.{engine}", "1")
