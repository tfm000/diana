"""Wave-0 RED/skip scaffold for the torch-free GPU gate (Plan 06, Fish/HEAVY-03).

D-09/D-10: Fish S2 Pro needs an NVIDIA GPU with ~12+ GB VRAM. The capability must
be detected on the cheap badge path WITHOUT importing torch (Pitfall 4 — no
``torch.cuda.is_available()``), so the gate shells ``nvidia-smi`` and parses
``memory.total`` (RESEARCH Pattern 4). These tests mock ``shutil.which`` /
``subprocess.run`` (the ``fake_nvidia_smi`` fixture) and assert:

  - absent GPU  -> ``(False, 0, <reason>)``
  - below floor -> ``(False, _, <reason>)``
  - at/above floor -> ``(True, vram_gb, "")``
  - and ``torch`` is NEVER imported by the call (ENGINE-01 / D-09).

``capable_nvidia_gpu`` + ``FISH_MIN_VRAM_GB`` land in Wave 6 (module home
``diana.tts.gpu_probe``); collection stays GREEN until then.
"""

import sys

import pytest

# --- Guarded probe: the GPU gate lands in Wave 6 ----------------------------
_capable_nvidia_gpu = None
_FISH_MIN_VRAM_GB = None
try:
    from diana.tts.gpu_probe import (  # noqa: F401
        FISH_MIN_VRAM_GB as _FISH_MIN_VRAM_GB,
        capable_nvidia_gpu as _capable_nvidia_gpu,
    )

    _GPU_PROBE_AVAILABLE = True
except (ImportError, AttributeError):
    _GPU_PROBE_AVAILABLE = False


def _assert_no_torch():
    """The badge path must never pull torch into the app interpreter (Pitfall 4)."""
    assert "torch" not in sys.modules, "GPU gate must not import torch (D-09)"


# --- D-09: the VRAM floor is in the researched 12-24 GB band ----------------
@pytest.mark.skipif(
    not _GPU_PROBE_AVAILABLE, reason="capable_nvidia_gpu lands in Wave 6"
)
def test_fish_min_vram_floor_sane():
    """FISH_MIN_VRAM_GB is the researched NVIDIA floor (12 min / 24 recommended)."""
    assert 8 <= _FISH_MIN_VRAM_GB <= 24


# --- D-10: no nvidia-smi -> shown-but-disabled with a reason ----------------
@pytest.mark.skipif(
    not _GPU_PROBE_AVAILABLE, reason="capable_nvidia_gpu lands in Wave 6"
)
def test_absent_gpu_reports_reason(fake_nvidia_smi):
    """No ``nvidia-smi`` on PATH -> (False, 0, <non-empty reason>), no torch."""
    fake_nvidia_smi(None)
    ok, vram, reason = _capable_nvidia_gpu()
    assert ok is False
    assert vram == 0
    assert reason, "an absent GPU must carry an actionable reason (D-10)"
    _assert_no_torch()


# --- below the floor -> disabled with a reason ------------------------------
@pytest.mark.skipif(
    not _GPU_PROBE_AVAILABLE, reason="capable_nvidia_gpu lands in Wave 6"
)
def test_below_floor_gpu_disabled(fake_nvidia_smi):
    """A GPU below FISH_MIN_VRAM_GB is rejected with a reason (D-10)."""
    fake_nvidia_smi(int((_FISH_MIN_VRAM_GB - 4) * 1024))  # MiB, ~4 GB under floor
    ok, _vram, reason = _capable_nvidia_gpu()
    assert ok is False
    assert reason
    _assert_no_torch()


# --- at/above the floor -> capable, no reason -------------------------------
@pytest.mark.skipif(
    not _GPU_PROBE_AVAILABLE, reason="capable_nvidia_gpu lands in Wave 6"
)
def test_above_floor_gpu_capable(fake_nvidia_smi):
    """A GPU at/above the floor -> (True, vram_gb>=floor, "") and no torch import."""
    fake_nvidia_smi(int((_FISH_MIN_VRAM_GB + 4) * 1024))  # MiB, ~4 GB over floor
    ok, vram, reason = _capable_nvidia_gpu()
    assert ok is True
    assert vram >= _FISH_MIN_VRAM_GB
    assert not reason, "a capable GPU carries no disabled-reason"
    _assert_no_torch()


# --- non-zero returncode -> disabled even if stdout has numeric text ---------
@pytest.mark.skipif(
    not _GPU_PROBE_AVAILABLE, reason="capable_nvidia_gpu lands in Wave 6"
)
def test_nonzero_returncode_reports_disabled(fake_nvidia_smi):
    """nvidia-smi exits non-zero -> (False, 0, reason) even if stdout looks numeric.

    A degraded NVIDIA driver may emit partial numeric text on stdout while exiting
    with a non-zero code. The gate must NOT parse that text — returncode is checked
    BEFORE parsing so a false-capable result is never returned (CR-01).
    """
    # Simulate a GPU that would appear capable (24 GB) if stdout were parsed,
    # but the driver is degraded and the process exits with code 1.
    fake_nvidia_smi(int((_FISH_MIN_VRAM_GB + 12) * 1024), returncode=1)
    ok, vram, reason = _capable_nvidia_gpu()
    assert ok is False, "a non-zero nvidia-smi exit must return not-capable"
    assert vram == 0
    assert reason, "a failed query must carry a reason (D-10)"
    _assert_no_torch()
