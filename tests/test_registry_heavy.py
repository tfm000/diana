"""Wave-0 RED/skip scaffold for heavy-engine registry wiring (Plan 04, D-17).

D-17 / ENGINE-01: the three heavy engines (orpheus/f5/fish) must register in
``diana.tts.registry`` and surface in the cross-engine browser like Kokoro/Piper —
WITHOUT pulling torch/llama-cpp/orpheus_cpp/f5_tts onto the cheap enumeration/badge
path (those SDKs live only in the per-engine venv, reached by subprocess).

The ``test_cheap_enumeration_imports_no_heavy_sdk`` gate is deliberately UNGATED:
it is a live regression gate from day one (Waves 2-7) — the moment a registry edit
accidentally imports a heavy SDK on the cheap path, this fails. The engine-name /
ASCII-map assertions are ``skipif``-gated on the heavy engines being registered
(Wave 2), then flip green with zero edits.
"""

import sys

import pytest

from diana.tts import registry

_HEAVY_SDKS = ("torch", "llama_cpp", "orpheus_cpp", "f5_tts")
_HEAVY_ENGINES = ("orpheus", "f5", "fish")
_HEAVY_REGISTERED = "orpheus" in registry.list_engines()


# --- ENGINE-01 / D-17: cheap enumeration imports NO heavy SDK (UNGATED) -----
def test_cheap_enumeration_imports_no_heavy_sdk():
    """list_engines() + engine_is_ascii_only() pull no torch/llama/orpheus/f5 import."""
    before = {m for m in _HEAVY_SDKS if m in sys.modules}
    engines = registry.list_engines()
    for name in engines:
        registry.engine_is_ascii_only(name)
    after = {m for m in _HEAVY_SDKS if m in sys.modules}
    newly = after - before
    assert not newly, f"cheap registry path newly imported heavy SDK(s): {newly}"


# --- D-17: the three heavy engines are listed (badge/gate cheaply) ----------
@pytest.mark.skipif(
    not _HEAVY_REGISTERED, reason="heavy engines register in Wave 2"
)
def test_heavy_engines_listed():
    """list_engines() includes orpheus/f5/fish alongside the light engines."""
    engines = registry.list_engines()
    for name in _HEAVY_ENGINES:
        assert name in engines


# --- D-17: heavy engines are UTF-8 capable (not ASCII-only) -----------------
@pytest.mark.skipif(
    not _HEAVY_REGISTERED, reason="heavy engines register in Wave 2"
)
def test_heavy_engines_are_utf8_capable():
    """Neural engines speak UTF-8 -> _ASCII_ONLY_ENGINES maps each to False."""
    for name in _HEAVY_ENGINES:
        assert registry._ASCII_ONLY_ENGINES.get(name) is False
        assert registry.engine_is_ascii_only(name) is False
