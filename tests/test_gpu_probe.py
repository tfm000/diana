"""Torch-free GPU capability gate for Fish S2 Pro — TRI-STATE (Plan 06 + quick-260616-hk6).

D-09/D-10 (corrected): Fish S2 Pro runs FULL-SUPPORT on an NVIDIA GPU with ~12+ GB VRAM,
EXPERIMENTAL on Apple Silicon (>=16 GB unified) via Metal/MPS (fish-speech has native MPS
support — PR #461), and is otherwise disabled with an honest reason. The capability must be
resolved on the cheap badge path WITHOUT importing torch (Pitfall 4 — no
``torch.cuda.is_available()``): the gate shells ``nvidia-smi`` (``memory.total``) and
``sysctl -n hw.memsize`` (RESEARCH Pattern 4) — both stdlib subprocess, never torch.

``capable_nvidia_gpu`` (unchanged contract — the "cuda" probe) and the new tri-state
``fish_capability`` -> ``(tier, label, reason)`` with tier in {"cuda","apple","none"} are
asserted below. Every ``fish_capability`` branch asserts ``"torch" not in sys.modules``.
"""

import sys

import pytest

# --- Guarded probe: the GPU gate lands in Wave 6 ----------------------------
_capable_nvidia_gpu = None
_fish_capability = None
_FISH_MIN_VRAM_GB = None
_APPLE_MIN_UNIFIED_GB = None
try:
    from diana.tts.gpu_probe import (  # noqa: F401
        APPLE_MIN_UNIFIED_GB as _APPLE_MIN_UNIFIED_GB,
        FISH_MIN_VRAM_GB as _FISH_MIN_VRAM_GB,
        capable_nvidia_gpu as _capable_nvidia_gpu,
        fish_capability as _fish_capability,
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


# --- The Apple unified-memory floor is the researched 16 GB ----------------
@pytest.mark.skipif(
    not _GPU_PROBE_AVAILABLE, reason="fish_capability lands in Wave 6"
)
def test_apple_min_unified_floor_sane():
    """APPLE_MIN_UNIFIED_GB is the researched Apple Silicon floor (16 GB unified)."""
    assert _APPLE_MIN_UNIFIED_GB == 16


# --- D-10: no nvidia-smi -> capable_nvidia_gpu shown-but-disabled with a reason ---
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


# ---------------------------------------------------------------------------
# Tri-state fish_capability() — {cuda, apple, none} (quick-260616-hk6)
# ---------------------------------------------------------------------------


def _force_darwin_arm64(monkeypatch, machine="arm64", platform_name="darwin"):
    """Mock a darwin/arm64 host so the Apple branch of fish_capability is reachable."""
    import platform as _platform

    monkeypatch.setattr(sys, "platform", platform_name, raising=False)
    monkeypatch.setattr(_platform, "machine", lambda: machine)


def _force_unified_memory(monkeypatch, gb):
    """Stub the private Apple unified-memory reader to a fixed GB value (torch-free)."""
    import diana.tts.gpu_probe as _gp

    monkeypatch.setattr(_gp, "_apple_unified_gb", lambda: gb)


# --- tier "cuda": a capable NVIDIA GPU -> full support ----------------------
@pytest.mark.skipif(
    not _GPU_PROBE_AVAILABLE, reason="fish_capability lands in Wave 6"
)
def test_fish_capability_cuda_tier(fake_nvidia_smi):
    """A capable NVIDIA GPU (>=12 GB) -> tier 'cuda', empty/positive reason, no torch."""
    fake_nvidia_smi(int((_FISH_MIN_VRAM_GB + 4) * 1024))  # MiB, over the floor
    tier, label, reason = _fish_capability()
    assert tier == "cuda"
    assert label, "the cuda tier must carry a short label"
    assert not reason, "a fully-supported NVIDIA GPU carries no disabled reason"
    _assert_no_torch()


# --- tier "apple": arm64 macOS with >=16 GB unified -> experimental ---------
@pytest.mark.skipif(
    not _GPU_PROBE_AVAILABLE, reason="fish_capability lands in Wave 6"
)
def test_fish_capability_apple_tier(fake_nvidia_smi, monkeypatch):
    """arm64 darwin + >=16 GB unified, no nvidia-smi -> tier 'apple', experimental reason."""
    fake_nvidia_smi(None)  # no NVIDIA GPU
    _force_darwin_arm64(monkeypatch)
    _force_unified_memory(monkeypatch, _APPLE_MIN_UNIFIED_GB + 32)  # plenty of RAM
    tier, label, reason = _fish_capability()
    assert tier == "apple"
    assert label, "the apple tier must carry a short label"
    low = reason.lower()
    assert "apple" in low or "mps" in low or "metal" in low, (
        f"the apple reason must mention Apple Silicon / Metal / MPS, got: {reason!r}"
    )
    assert "experimental" in low, (
        f"the apple tier must be flagged EXPERIMENTAL, got: {reason!r}"
    )
    _assert_no_torch()


# --- tier "none": no NVIDIA + under-spec/non-arm64 -> honest dual reason -----
@pytest.mark.skipif(
    not _GPU_PROBE_AVAILABLE, reason="fish_capability lands in Wave 6"
)
def test_fish_capability_none_tier_under_spec_mac(fake_nvidia_smi, monkeypatch):
    """arm64 darwin but <16 GB unified, no nvidia-smi -> tier 'none', dual NVIDIA+Apple reason."""
    fake_nvidia_smi(None)  # no NVIDIA GPU
    _force_darwin_arm64(monkeypatch)
    _force_unified_memory(monkeypatch, 8)  # below the 16 GB Apple floor
    tier, _label, reason = _fish_capability()
    assert tier == "none"
    low = reason.lower()
    assert "nvidia" in low, f"the none reason must name an NVIDIA GPU, got: {reason!r}"
    assert "apple" in low, f"the none reason must name Apple Silicon, got: {reason!r}"
    _assert_no_torch()


@pytest.mark.skipif(
    not _GPU_PROBE_AVAILABLE, reason="fish_capability lands in Wave 6"
)
def test_fish_capability_none_tier_non_apple(fake_nvidia_smi, monkeypatch):
    """A non-darwin/non-arm64 host with no NVIDIA GPU -> tier 'none', dual reason, no torch."""
    fake_nvidia_smi(None)  # no NVIDIA GPU
    _force_darwin_arm64(monkeypatch, machine="x86_64", platform_name="linux")
    tier, _label, reason = _fish_capability()
    assert tier == "none"
    low = reason.lower()
    assert "nvidia" in low and "apple" in low, (
        f"the none reason must name BOTH NVIDIA and Apple Silicon, got: {reason!r}"
    )
    # A flat NVIDIA-only claim is exactly the false-on-Mac wording this change retires.
    assert low.strip() != "requires an nvidia gpu with ~12+ gb vram (none detected)"
    _assert_no_torch()
