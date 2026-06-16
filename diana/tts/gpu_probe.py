"""Torch-free GPU capability gate for Fish S2 Pro — TRI-STATE (D-09 corrected / D-10).

Fish S2 Pro has three capability tiers, resolved WITHOUT importing torch (ENGINE-01: no
``torch.cuda.is_available()`` on the enumeration path — that would pull a multi-GB dep into
the app interpreter and is slow). The gate shells OS-provided tools and parses their output
(RESEARCH Pattern 4) — the same "resolve a capability cheaply, no engine SDK" lane as
``install_state``:

  * **NVIDIA (full support):** a present NVIDIA GPU with ~12+ GB VRAM, detected via
    ``nvidia-smi`` (``memory.total``). The fast paths (``--compile``/Triton, the SGLang
    streaming engine) are CUDA-only, so this is the first-class path.
  * **Apple Silicon (EXPERIMENTAL):** arm64 macOS with >=16 GB unified memory, read via
    ``sysctl -n hw.memsize``. fish-speech has native MPS support (PR #461, merged
    2024-08-15) so it RUNS on Apple Silicon via Metal/MPS — but S2-Pro-on-MPS is unverified
    upstream and slower than CUDA, so it is offered as EXPERIMENTAL (runs, may be slow /
    unstable), never first-class. The earlier "effectively unsupported on macOS" framing was
    false; the flat NVIDIA-only claim is retired.
  * **otherwise (disabled):** neither a capable NVIDIA GPU nor capable Apple Silicon — the
    row is SHOWN BUT DISABLED with an honest reason naming BOTH options (D-10), never hidden
    and never a flat "requires NVIDIA" claim.

``capable_nvidia_gpu()`` is the NVIDIA probe (unchanged contract); ``fish_capability()`` is
the tri-state resolver that callers (the engine gate + the Settings/Upload badge sites) use.
"""

import platform
import shutil
import subprocess
import sys

# The researched NVIDIA floor for Fish S2 Pro: 12 GB minimum, 24 GB recommended.
FISH_MIN_VRAM_GB = 12

# The Apple Silicon unified-memory floor for the EXPERIMENTAL MPS path: 16 GB.
APPLE_MIN_UNIFIED_GB = 16


def capable_nvidia_gpu() -> tuple[bool, float, str]:
    """Return ``(ok, vram_gb, reason)`` using ``nvidia-smi`` only — no torch import.

    ``ok`` is True iff a present NVIDIA GPU reports >= ``FISH_MIN_VRAM_GB`` of total
    VRAM. When no ``nvidia-smi`` is on PATH (e.g. Apple Silicon / no NVIDIA driver),
    or the query fails, or the GPU is below the floor, ``ok`` is False and ``reason``
    is a short, NVIDIA-probe string. A capable GPU carries an empty reason.

    This is now the "cuda" PROBE consumed by :func:`fish_capability`; its reason strings
    are never shown verbatim as a Mac's disabled reason — the honest user-facing dual
    reason is owned by :func:`fish_capability`'s "none" tier.
    """
    smi = shutil.which("nvidia-smi")
    if not smi:
        return False, 0, "no NVIDIA GPU detected"
    try:
        out = subprocess.run(
            [smi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return False, 0, "could not query GPU memory"
        vram_gb = max(int(x) for x in out.stdout.split()) / 1024
    except Exception:
        return False, 0, "could not query GPU memory"
    ok = vram_gb >= FISH_MIN_VRAM_GB
    return ok, vram_gb, ("" if ok else f"requires ~{FISH_MIN_VRAM_GB}+ GB VRAM (found ~{vram_gb:.0f} GB)")


def _apple_unified_gb() -> int:
    """Total Apple unified memory in GB via ``sysctl -n hw.memsize`` — torch-free.

    Shells the OS-provided ``sysctl`` (fixed argv, ``shell=False``, short timeout — the
    same defensive lane as :func:`capable_nvidia_gpu`'s ``nvidia-smi`` parse; no user input
    reaches the command) and parses the integer byte count, ``// 1024**3`` for GB. Returns
    ``0`` on any failure (missing binary, non-zero exit, unparsable output) so the caller
    treats an unreadable host as not-capable rather than raising.
    """
    sysctl = shutil.which("sysctl")
    if not sysctl:
        return 0
    try:
        out = subprocess.run(
            [sysctl, "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return 0
        return int(out.stdout.strip()) // (1024 ** 3)
    except Exception:
        return 0


def fish_capability() -> tuple[str, str, str]:
    """Resolve the Fish capability tri-state ``(tier, label, reason)`` — torch-free.

    ``tier`` is one of ``{"cuda", "apple", "none"}`` (resolution order cuda -> apple -> none):

      * ``"cuda"`` — a capable NVIDIA GPU (>= ``FISH_MIN_VRAM_GB``), decided by
        :func:`capable_nvidia_gpu`. Full support; ``reason`` is empty.
      * ``"apple"`` — arm64 macOS with >= ``APPLE_MIN_UNIFIED_GB`` unified memory.
        EXPERIMENTAL: the reason states it runs on Apple Silicon via Metal/MPS but is
        experimental, slower than NVIDIA, and unsupported upstream.
      * ``"none"`` — neither; the reason names BOTH a capable NVIDIA GPU (~12+ GB VRAM) AND
        Apple Silicon (16+ GB unified) — never a flat NVIDIA-only claim.

    Stdlib-only (``shutil``/``subprocess``/``sys``/``platform``), torch-free.
    """
    ok_gpu, _vram, _reason = capable_nvidia_gpu()
    if ok_gpu:
        return "cuda", "NVIDIA GPU", ""
    if (
        sys.platform == "darwin"
        and platform.machine() == "arm64"
        and _apple_unified_gb() >= APPLE_MIN_UNIFIED_GB
    ):
        return (
            "apple",
            "Apple Silicon (MPS)",
            "experimental on Apple Silicon — runs via Metal/MPS, slower than NVIDIA, "
            "unsupported upstream",
        )
    return (
        "none",
        "GPU required",
        f"requires an NVIDIA GPU (~{FISH_MIN_VRAM_GB}+ GB VRAM) or Apple Silicon "
        f"({APPLE_MIN_UNIFIED_GB}+ GB unified memory)",
    )
