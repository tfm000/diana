"""Torch-free GPU capability gate for Fish S2 Pro — NO heavy import (D-09/D-10).

Fish S2 Pro is NVIDIA-CUDA-focused and needs ~12+ GB VRAM (RESEARCH HEAVY-03 /
Pitfall 4). The cheap badge/gate path must detect a capable GPU WITHOUT importing
torch (ENGINE-01: no ``torch.cuda.is_available()`` on the enumeration path — that
would pull a multi-GB dep into the app interpreter and is slow). So the gate shells
the OS-provided ``nvidia-smi`` and parses ``memory.total`` (RESEARCH Pattern 4) —
the same "resolve a capability cheaply, no engine SDK" lane as ``install_state``.

Intentionally NVIDIA-CUDA-ONLY: Apple Silicon has no ``nvidia-smi`` (and fish-speech
is effectively unsupported on macOS, with a VRAM floor above typical Mac unified-
memory budgets), so on a Mac the gate returns not-capable and Fish is SHOWN BUT
DISABLED with the reason string (D-10) — never silently hidden.
"""

import shutil
import subprocess

# The researched NVIDIA floor for Fish S2 Pro: 12 GB minimum, 24 GB recommended.
FISH_MIN_VRAM_GB = 12


def capable_nvidia_gpu() -> tuple[bool, float, str]:
    """Return ``(ok, vram_gb, reason)`` using ``nvidia-smi`` only — no torch import.

    ``ok`` is True iff a present NVIDIA GPU reports >= ``FISH_MIN_VRAM_GB`` of total
    VRAM. When no ``nvidia-smi`` is on PATH (e.g. Apple Silicon / no NVIDIA driver),
    or the query fails, or the GPU is below the floor, ``ok`` is False and ``reason``
    is a short, user-facing string for the shown-but-disabled row (D-10). A capable
    GPU carries an empty reason.
    """
    smi = shutil.which("nvidia-smi")
    if not smi:
        return False, 0, "requires an NVIDIA GPU with ~12+ GB VRAM (none detected)"
    try:
        out = subprocess.run(
            [smi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        vram_gb = max(int(x) for x in out.stdout.split()) / 1024
    except Exception:
        return False, 0, "could not query GPU memory"
    ok = vram_gb >= FISH_MIN_VRAM_GB
    return ok, vram_gb, ("" if ok else f"requires ~{FISH_MIN_VRAM_GB}+ GB VRAM (found ~{vram_gb:.0f} GB)")
