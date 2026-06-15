---
phase: 05-heavy-opt-in-engines
verified: 2026-06-15T22:21:20Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Orpheus real install + by-ear synthesis (HEAVY-01)"
    expected: "Install button shows itemized footprint (~2.3 GB+). Two-phase progress completes: Phase A (uv venv + pip install), Phase B (GGUF + SNAC weights). Row shows 'Ready · Orpheus installed'. Audio converts with a named voice (e.g., Tara) and sounds like Orpheus neural TTS by ear."
    why_human: "Real multi-GB install (GGUF ~2.3 GB + deps) requires a macOS or Windows machine where a multi-GB download is feasible. No NVIDIA GPU needed (CPU-viable). Logic verified with mocked subprocess; real synth cannot run in an automated session on this dev box."
  - test: "F5-TTS real install + accept-license + by-ear synthesis (HEAVY-02)"
    expected: "Settings > Voices F5 row shows CC-BY-NC non-commercial disclosure + Read the license link (github.com/SWivid/F5-TTS) + 'I accept' BEFORE any Install control. After acceptance, itemized footprint (~3 GB torch deps + ~1.4 GB model). Two-phase install completes. Audio converts with Default (F5) voice and sounds like F5 cloning by ear. Re-open: license NOT re-prompted (accept-once persisted). Default engines (native_os/Kokoro/Piper) still work."
    why_human: "Real multi-GB torch + F5TTS_v1_Base install. Logic verified with mocked subprocess and AppTest; real torch inference cannot run in automated session."
  - test: "F5 Custom Voices real F5-clone by ear (HEAVY-02, Plan 05-06)"
    expected: "Upload or record a reference clip + transcript in Settings > Voices > Custom Voices. Clip saved to library, appears in Upload picker and Browse-all table. Select that custom voice in Upload + convert a short .txt: audio sounds like the cloned reference voice, not the bundled default and not silence. Remove with in-use block honored."
    why_human: "The actual F5 zero-shot clone inference requires the torch venv (multi-GB install). The capture/validate/save/remove/enumerate logic and picker/browser appearance are automated-tested; only real clone synthesis is deferred."
  - test: "Bundled F5 default clip provenance confirmation (Q-E)"
    expected: "Listen to diana/data/voices/f5_default.wav and read f5_default.txt. Clip is self-generated on-device with macOS say (license-clean by construction). Developer confirms provenance is acceptable for shipping, or replaces with a public-domain/self-recorded clip + exact transcript (~6-12 s mono)."
    why_human: "Provenance is a human judgment call, not automatically verifiable. File is confirmed present and readable (6.55 s, 22.05 kHz, mono PCM_16); transcript is non-empty."
  - test: "Fish S2 Pro GPU gate opens on NVIDIA >= 12 GB machine + real install + by-ear synthesis (HEAVY-03)"
    expected: "On an NVIDIA >= 12 GB VRAM machine: Fish row is ENABLED (no disabled state). Fish Audio Research License / CC-BY-NC-SA-4.0 disclosure shown + Read the license link (huggingface.co/fishaudio/s2-pro) + 'I accept' before any Install. Accept-once persisted. Two-phase install (git+SHA fish-speech + s2-pro weights) completes. Audio converts with the default or custom voice by ear. MEDIUM-confidence item: confirm the fish_worker.py TTSInferenceEngine/ServeTTSRequest API shape against the installed package; adjust if it differs."
    why_human: "Fish S2 Pro is NVIDIA-CUDA-only (~12-24 GB VRAM). This macOS dev box has no NVIDIA GPU so the GPU gate correctly shows the engine SHOWN-BUT-DISABLED. That no-GPU path is verified live; only the CUDA-machine install + synth requires an NVIDIA box."
---

# Phase 5: Heavy Opt-In Engines Verification Report

**Phase Goal:** Power users can opt into higher-quality neural engines (Orpheus, F5-TTS, and GPU-gated Fish S2 Pro) as on-demand installs layered on the Phase 4 substrate, with licensing surfaced before download and no impact on the lightweight default install.
**Verified:** 2026-06-15T22:21:20Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can install and synthesize with Orpheus (llama-cpp-python + GGUF, CPU-viable) using its named voices | VERIFIED (logic) / DEFERRED (real install) | `OrpheusEngine.VOICES` = 8 named TTSVoice with no orpheus_cpp import. `initialize()` raises FileNotFoundError pointing to Settings > Voices when uninstalled. `synthesize` shells `[venv-python, orpheus_worker.py]` with text as stdin JSON. Install row in Settings with itemized footprint + two-phase progress. `test_orpheus_engine.py` + `test_orpheus_slice_apptest.py` pass (3/3). Real multi-GB install deferred to HUMAN-UAT. |
| 2 | User can install F5-TTS on demand, see and accept an in-app non-commercial license disclosure before download, and clone a voice from a validated reference-audio clip | VERIFIED (logic + license gate + bundled default + clip validation) / DEFERRED (real torch install + clone by ear) | NC license gate (CC-BY-NC, D-08) shown BEFORE any Install control, accepted-once persisted in app_settings, engine-scoped. Bundled default voice `f5_default.wav` (6.55 s, 22.05 kHz, mono PCM_16) + exact `f5_default.txt` transcript ship as package data. `validate_clip` returns `(bool, msg)` never raises. Custom Voices section in Settings has Upload + Record tabs. `test_f5_engine.py` + `test_f5_slice_apptest.py` + `test_custom_voices.py` + `test_license_gate.py` pass. Real torch install + F5-clone synthesis deferred. |
| 3 | Fish Audio S2 Pro is shown but disabled with a 'requires a capable GPU (~12+ GB VRAM)' reason when none is detected; when shown it is opt-in and presents its non-commercial license disclosure before download | VERIFIED (shown-but-disabled live path + license gate logic) / DEFERRED (real GPU-machine install + synth) | `capable_nvidia_gpu()` on this macOS box returns `(False, 0, "requires an NVIDIA GPU with ~12+ GB VRAM (none detected)")`. Settings Fish row renders SHOWN with DISABLED Install + reason caption (NOT hidden). Upload badge surfaces GPU reason. NC license (Fish Audio Research License / CC-BY-NC-SA-4.0) shown behind GPU gate before any Install. D-10 wording reconciled in REQUIREMENTS.md HEAVY-03 and ROADMAP.md SC#3 to "shown but disabled". `test_fish_slice_apptest.py` (5 tests) exercise both the live no-GPU path and a mocked GPU-ok path. |
| 4 | Choosing a heavy engine without its model installed fails fast with an actionable prompt rather than erroring mid-job | VERIFIED | `heavy_engine_failfast("orpheus")` returns `"Orpheus isn't installed — open Settings ▸ Voices and click Install."` (live behavior verified). Returns `None` for kokoro/piper/native_os (non-heavy). In `1_Upload.py`: `_failfast = heavy_engine_failfast(engine_name)` → `st.error(_failfast)` and `disabled=bool(_failfast)` on the Convert button. AppTest tests verify the actionable prompt and Convert disabled=True for all three heavy engines. No torch/llama_cpp imported on this check path. |

**Score:** 4/4 truths verified (logic and wiring complete; human UAT deferred for real multi-GB installs and GPU-machine synthesis per Phase-3/4 precedent)

### Deferred Items

Items not yet met but explicitly deferred to HUMAN-UAT, NOT a later milestone phase.

| # | Item | Deferred To | Evidence |
|---|------|-------------|----------|
| 1 | Orpheus real install + by-ear synthesis | 05-HUMAN-UAT.md | Multi-GB install impractical on macOS dev box. Logic fully automated-tested (subprocess mocked). Steps documented in HUMAN-UAT HEAVY-01. |
| 2 | F5 real install + by-ear synthesis | 05-HUMAN-UAT.md | Multi-GB torch install impractical on macOS dev box. Logic + license gate automated-tested. Steps documented in HUMAN-UAT HEAVY-02. |
| 3 | F5 Custom Voices real clone by ear | 05-HUMAN-UAT.md | Requires installed torch venv. Capture/validate/save/remove/enumerate logic automated-tested. Steps documented in HUMAN-UAT HEAVY-02 (Custom Voices section). |
| 4 | F5 bundled default clip provenance (Q-E) | 05-HUMAN-UAT.md | Human judgment call on license-clean provenance. File confirmed present + readable. Steps documented in HUMAN-UAT HEAVY-02 step 6. |
| 5 | Fish real GPU install + by-ear synthesis | 05-HUMAN-UAT.md | NVIDIA >= 12 GB VRAM machine required. The no-GPU shown-but-disabled path is verified LIVE on this machine. Steps documented in HUMAN-UAT HEAVY-03. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `diana/tts/gpu_probe.py` | Torch-free nvidia-smi VRAM gate | VERIFIED | `capable_nvidia_gpu()` → `(False, 0, reason)` on this box. `FISH_MIN_VRAM_GB = 12`. No torch import. 44 lines, substantive. |
| `diana/paths.py` | venvs_dir/hf_cache_dir/custom_voices_dir/uv_binary/heavy_worker | VERIFIED | All five functions present; `venvs_dir`, `hf_cache_dir`, `custom_voices_dir` appear in `ensure_dirs()`. `uv_binary()` and `heavy_worker()` resolve package resources. |
| `diana/tts/install_state.py` | heavy_engine_installed/heavy_footprint_bytes/uninstall_heavy_engine | VERIFIED | All three functions present. `heavy_engine_installed("orpheus")` returns False on dev box (no venv/marker). Filesystem-only probe — no torch/llama_cpp imported. 227 lines with Phase-5 section clearly demarcated. |
| `diana/tts/heavy_install.py` | Two-phase provisioner + accept-once license gate | VERIFIED | `HeavyInstallSpec` dataclass, `_BUILTIN_SPECS` (orpheus/f5/fish pins), `provision_venv` (`uv venv` + `uv pip install`), `install_engine` (disk pre-check → deps → weights → marker), `license_accepted`/`accept_license` (DB-backed, lazy import). 299 lines. |
| `diana/tts/registry.py` | `_HEAVY_ENGINES`, ASCII map entries, `heavy_engine_failfast`, heavy engines in `list_engines()` | VERIFIED | `_HEAVY_ENGINES = {"orpheus", "f5", "fish"}`. All three in `_ASCII_ONLY_ENGINES` as `False`. `heavy_engine_failfast` returns actionable message or None. `list_engines()` returns all 6 including heavy. `all_engine_voices()` enumerates heavy engine voices with no heavy import. |
| `diana/tts/orpheus_engine.py` | OrpheusEngine with 8 VOICES, fail-fast initialize, subprocess synth | VERIFIED | 8 VOICES defined (tara/leah/jess/mia/zoe/leo/dan/zac), all tier="enhanced", en-us. `initialize()` raises `FileNotFoundError` naming Settings > Voices. `synthesize` shells venv python with stdin JSON (T-05-CMD). No orpheus_cpp/llama_cpp at module level. |
| `diana/tts/f5_engine.py` | F5Engine with bundled default voice, NC-license install, subprocess synth, custom voice resolution | VERIFIED | `F5Engine.VOICES = [TTSVoice("f5_default", "Default (F5)", ...)]`. `initialize()` fail-fasts. `_resolve_ref` handles bundled default + custom voices. `synthesize` shells torch venv python with stdin JSON. `f5_install_spec()` returns HeavyInstallSpec. No torch/f5_tts at module level. |
| `diana/tts/fish_engine.py` | FishEngine with GPU gate in initialize, NC-license, subprocess synth | VERIFIED | `initialize()` checks BOTH `heavy_engine_installed("fish")` AND `capable_nvidia_gpu()`. `_resolve_ref` handles bundled default (reuses f5_default) + custom voices. `fish_install_spec()` returns HeavyInstallSpec with git+SHA pin. No torch/fish_speech at module level. |
| `diana/tts/custom_voices.py` | validate_clip, safe_custom_voice_dest, save/list/remove_custom_voice, custom_voice_ref | VERIFIED | All functions present. `validate_clip` never raises, returns `(bool, msg)`. `safe_custom_voice_dest` strips path components + enforces .wav/.mp3/.txt allow-list + containment check. `list_custom_voices` tolerates malformed metadata. `remove_custom_voice` checks `voice_in_use` across f5+fish. 385 lines. |
| `diana/tts/heavy_workers/orpheus_worker.py` | Out-of-process worker (run by venv python) | VERIFIED | 56 lines. Imports `orpheus_cpp` (only when run by venv python). `--prefetch` mode + synthesis mode. stdin JSON → WAV write. |
| `diana/tts/heavy_workers/f5_worker.py` | Out-of-process F5 worker | VERIFIED | 77 lines. Imports `f5_tts` (venv python only). `--prefetch` + synthesis. stdin JSON with ref_file/ref_text/gen_text → WAV write. |
| `diana/tts/heavy_workers/fish_worker.py` | Out-of-process Fish worker | VERIFIED | 133 lines. Imports fish_speech (venv python only). `--prefetch` + synthesis. MEDIUM-confidence inference API (deferred to HUMAN-UAT step 3). |
| `diana/data/voices/f5_default.wav` | Bundled license-clean default reference clip (D-15) | VERIFIED | Exists (292,884 bytes). `soundfile.info()` reads 6.55 s, 22050 Hz, mono PCM_16. |
| `diana/data/voices/f5_default.txt` | Bundled default clip transcript | VERIFIED | Exists. Non-empty transcript: "The quiet morning light spread across the valley..." |
| `diana/dashboard/pages/5_Settings.py` | Heavy engine install rows + license gate + GPU gate + Custom Voices section | VERIFIED | `_render_heavy_engine_row` is the generic row. Orpheus row at line 1790 (no license). F5 row at 1795 with CC-BY-NC license dict. Fish row at 1813 with CC-BY-NC-SA-4.0 license dict + `gpu_gate=gpu_probe.capable_nvidia_gpu()`. Custom Voices subheader at 1974 with Upload + Record tabs using `st.audio_input`. All inside `with tab_voices:`. |
| `diana/dashboard/pages/1_Upload.py` | `heavy_engine_failfast` wired to Convert button disabled state + readiness note per heavy engine | VERIFIED | `heavy_engine_failfast` imported at line 23. `_failfast = heavy_engine_failfast(engine_name)` at line 398. `st.error(_failfast)` + `disabled=bool(_failfast)` on Convert button at lines 400-405. `_engine_readiness` handles orpheus/f5/fish with cheap filesystem probes (lines 83-110). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `registry.heavy_engine_failfast` | `install_state.heavy_engine_installed` | lazy import inside function | WIRED | Confirmed: `from diana.tts.install_state import heavy_engine_installed` inside `heavy_engine_failfast`. No heavy SDK on this path. |
| `gpu_probe.capable_nvidia_gpu` | `nvidia-smi` | `shutil.which` + `subprocess.run --query-gpu=memory.total` | WIRED | Confirmed: `smi = shutil.which("nvidia-smi")`. Returns `(False, 0, reason)` on this box. No torch import. |
| `1_Upload.py` → Convert disabled | `registry.heavy_engine_failfast` | `_failfast = heavy_engine_failfast(engine_name); disabled=bool(_failfast)` | WIRED | Confirmed at lines 398-405. AppTest-verified: selecting uninstalled Orpheus/F5/Fish disables Convert + shows actionable prompt. |
| `5_Settings.py` Fish row | `gpu_probe.capable_nvidia_gpu` | `gpu_gate=gpu_probe.capable_nvidia_gpu()` argument to `_render_heavy_engine_row` | WIRED | Confirmed at line 1823. `_render_heavy_engine_row` uses `gpu_gate[0]` to gate shown-but-disabled. |
| `5_Settings.py` F5/Fish rows | `heavy_install.license_accepted` + `accept_license` | `_render_heavy_license_gate(engine, license)` which calls `heavy_install.license_accepted` | WIRED | Confirmed at lines 873-878. Accept-once persisted to `app_settings` via `set_setting(db_path, f"license.accepted.{engine}", "1")`. |
| `install_engine` (heavy_install) | `downloader.has_space` | `from diana.downloads import downloader; ok, free = downloader.has_space(venvs, needed)` | WIRED | Confirmed at lines 219-233 of heavy_install.py. Disk pre-check runs BEFORE any byte. |
| `install_engine` | `.{engine}.installed` marker | `(venvs / f".{spec.engine}.installed").write_text("1")` on success | WIRED | Confirmed at lines 275-276. `install_state.heavy_engine_installed` probes this same marker. |
| `F5Engine._resolve_ref` → custom voice | `custom_voices.custom_voice_ref` | lazy import inside `_resolve_ref` for non-default voice ids | WIRED | Confirmed at lines 141-146 of f5_engine.py. Same pattern in fish_engine.py. |
| `registry.all_engine_voices` | all six engines including orpheus/f5/fish | iterates `list_engines()` + calls `get_engine_voices(engine)` per engine | WIRED | Live test: `all_engine_voices()` returns voices from all 6 engines with no heavy import. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `5_Settings.py` Fish row | `gpu_gate` | `gpu_probe.capable_nvidia_gpu()` called at render time | Yes — live nvidia-smi probe | FLOWING (shown-but-disabled is the live real result on this box) |
| `5_Settings.py` heavy engine rows | `installed` | `install_state.heavy_engine_installed(engine)` | Yes — filesystem probe of venv+marker | FLOWING |
| `1_Upload.py` Convert button `disabled` | `_failfast` | `registry.heavy_engine_failfast(engine_name)` → `install_state.heavy_engine_installed` | Yes — filesystem probe | FLOWING |
| `F5Engine.synthesize` | `ref_file, ref_text` | `_resolve_ref(voice)` → bundled package resource or `custom_voices.custom_voice_ref` | Yes — package resource path resolved via importlib.resources | FLOWING |
| `OrpheusEngine.synthesize` | WAV bytes | venv subprocess stdout → temp WAV → `.read_bytes()` | Yes (mocked in tests; real subprocess path wired) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `heavy_engine_failfast("orpheus")` returns actionable message | `python3 -c "from diana.tts.registry import heavy_engine_failfast; print(heavy_engine_failfast('orpheus'))"` | `Orpheus isn't installed — open Settings ▸ Voices and click Install.` | PASS |
| `heavy_engine_failfast("kokoro")` returns None for non-heavy engine | Same script | `None` | PASS |
| GPU probe returns false + reason on no-NVIDIA box | `python3 -c "from diana.tts.gpu_probe import capable_nvidia_gpu; print(capable_nvidia_gpu())"` | `(False, 0, 'requires an NVIDIA GPU with ~12+ GB VRAM (none detected)')` | PASS |
| No heavy SDK on cheap path after registry + install_state calls | `python3 -c "import sys; sys.path.insert(0,'...'); import diana.tts.registry as r; import diana.tts.gpu_probe; import diana.tts.install_state; r.heavy_engine_failfast('orpheus'); ...; print(heavy_mods & set(sys.modules))"` | `NONE - clean` | PASS |
| `license_accepted` is engine-scoped, idempotent, persists across re-read | temp-DB round-trip in Python | accept f5 → f5 True, fish still False; re-accept idempotent; fresh connection still True | PASS |
| Full test suite stays green | `/Users/tyler/Repos/diana/.venv/bin/python -m pytest tests/ -q` | `512 passed, 1 deselected, 5 warnings` | PASS |
| Bundled F5 default clip is valid (6.55 s, 22050 Hz, non-empty transcript) | `soundfile.info()` + transcript read | 6.55 s, mono, 22050 Hz, transcript is 80+ chars | PASS |
| `all_engine_voices()` includes orpheus/f5/fish without heavy imports | live Python | all 6 engines in result, NONE heavy modules in sys.modules | PASS |

### Probe Execution

Step 7c: SKIPPED — no probe-*.sh scripts defined for Phase 5. The phase PLAN/SUMMARY declare no probes; verification uses AppTest interaction tests and the pytest suite instead.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| HEAVY-01 | 05-04 | Orpheus engine available (llama-cpp-python + GGUF, CPU-viable) with named voices | VERIFIED (logic) / DEFERRED (real install) | 8 named voices, no heavy import on cheap path, fail-fast wired, install row present, workers implemented. Real install deferred to HUMAN-UAT. |
| HEAVY-02 | 05-05, 05-06 | F5-TTS on-demand torch + reference-audio cloning + clip validation + NC-license disclosure before download | VERIFIED (logic + license gate + bundled default + clip validation) / DEFERRED (real torch install + clone by ear) | NC gate, bundled default, validate_clip, Custom Voices section, all tests pass. Real install deferred. |
| HEAVY-03 | 05-07 | Fish Audio S2 Pro GPU-gated (shown but disabled with reason), opt-in, NC-license disclosure | VERIFIED — the shown-but-disabled path IS the live path on this box | D-10 wording reconciled. Fish row shown-but-disabled live. NC license present behind GPU gate. AppTest (5 tests) covers no-GPU + mocked-GPU-ok paths. |

Note: REQUIREMENTS.md still shows HEAVY-01/02/03 as `[ ] Pending` — this is the normal pre-close-out state (same as Phase 4, where requirements were flipped after the verifier/roadmap-update pass). ROADMAP.md already shows Phase 5 as `[x] Complete (completed 2026-06-15)`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `heavy_workers/fish_worker.py` | inference call | MEDIUM-confidence API shape (TTSInferenceEngine/ServeTTSRequest) — noted in HUMAN-UAT step 3 | Warning | The fish_worker.py inference call shape is based on researched API; confirmed only at real-install time on a CUDA machine. Documented in HUMAN-UAT HEAVY-03 step 3 as a known open item. Not an unreferenced TBD — has a tracking note in the UAT. |

No `TBD`, `FIXME`, or `XXX` markers found in any Phase-5 source file. No stub return patterns (`return null`, `return []`, `return {}`) in functional code paths. No placeholder/hardcoded-empty props in the UI paths that render live data.

### Human Verification Required

The following items need human testing on a machine that supports large downloads or NVIDIA GPU synthesis. These mirror the Phase-3 (Windows) and Phase-4 (Piper import) deferred UAT precedent — the install/synthesis LOGIC is automated-tested with mocked subprocess; only real synthesis on capable hardware is deferred.

#### 1. Orpheus real install + by-ear synthesis (HEAVY-01)

**Test:** Open Settings > Voices > Engine models > Heavy opt-in engines > Orpheus. Confirm itemized footprint (~deps MB + ~model MB). Click Install twice (confirm then install). Watch two-phase progress (Phase A: "Installing dependencies…", Phase B: "Downloading model weights…"). Result should be "Ready · Orpheus installed". Go to Upload, select Orpheus + voice Tara, convert a short .txt, confirm audio plays and sounds like Orpheus neural TTS (not silence, not a different engine). Confirm native_os/Kokoro/Piper still work.
**Expected:** Install completes with no terminal. Audio converts and sounds like Orpheus neural voice by ear.
**Why human:** Multi-GB download (GGUF ~2.3 GB + deps) cannot run in automated session on this macOS dev box.

#### 2. F5-TTS real install + accept-license + by-ear synthesis (HEAVY-02)

**Test:** Open Settings > Voices > F5. Confirm CC-BY-NC disclosure + "Read the license" link (github.com/SWivid/F5-TTS) with NO Install control yet. Click "I accept". Confirm footprint confirm + Install appear. Install (two phases). Select F5 + Default (F5) in Upload, convert short .txt, confirm audio plays and sounds like F5 cloning. Re-open F5 row: license NOT re-prompted. Default engines unchanged.
**Expected:** License gate is blocking (no Install before acceptance), accept-once persisted, F5 installs and synthesizes by ear with no terminal.
**Why human:** Multi-GB torch + F5TTS_v1_Base install; real torch inference not runnable in automated session.

#### 3. Bundled F5 default clip provenance (Q-E)

**Test:** Listen to `diana/data/voices/f5_default.wav` and read `diana/data/voices/f5_default.txt`. The clip was self-generated on-device with macOS `say` (license-clean by construction). Confirm provenance is acceptable for shipping, or replace both files with a public-domain or self-recorded clip + exact transcript (~6-12 s, mono).
**Expected:** Provenance is acceptable (or clip is replaced with a clean one).
**Why human:** Provenance acceptability is a human judgment call.

#### 4. F5 Custom Voices real clone by ear (HEAVY-02)

**Test:** (F5 must already be installed.) In Settings > Voices > Custom Voices: record a clip via "Record a clip" tab or upload a .wav/.mp3 + transcript via "Upload a clip" tab. Name the voice. Confirm it appears in the library, Upload picker, and Browse-all table. Select it in Upload + convert a short .txt: audio should sound like the cloned reference voice. Deliberately submit a bad input (empty transcript, sub-1 s clip) and confirm rejection with a clear message. Remove the voice and confirm in-use block.
**Expected:** Custom voice capture, validation, clone synthesis by ear, and removal all work end-to-end with no terminal.
**Why human:** Real F5 clone synthesis requires the installed torch venv.

#### 5. Fish GPU gate opens on NVIDIA >= 12 GB machine + real install + by-ear synthesis (HEAVY-03)

**Test:** On an NVIDIA >= 12 GB VRAM machine: confirm Fish row is ENABLED (no disabled state). Accept Fish Audio Research License / CC-BY-NC-SA-4.0 disclosure (with "Read the license" link to huggingface.co/fishaudio/s2-pro). Install (shared torch venv). IMPORTANT: at this point confirm the fish_worker.py `TTSInferenceEngine`/`ServeTTSRequest` call shape against the installed fish-speech package — adjust the single inference call in `diana/tts/heavy_workers/fish_worker.py` if the real API differs. Convert a short .txt with Fish + default voice; confirm audio plays by ear. All other engines (native_os, Kokoro, Piper, Orpheus, F5) still work.
**Expected:** GPU gate opens on capable machine. NC license accepted once. Real synthesis completes by ear. No terminal used.
**Why human:** Requires NVIDIA GPU >= 12 GB VRAM. This macOS dev box has no NVIDIA GPU — the shown-but-disabled no-GPU path IS verified live; only the CUDA-machine install + synth is deferred.

---

### Gaps Summary

No gaps were found that prevent the phase goal from being achieved. All four success criteria are implemented and verified at the code and logic level:

1. Orpheus engine, 8 named voices, fail-fast gate, install machinery — fully implemented. Real install deferred to human UAT (legitimate, multi-GB).
2. F5-TTS NC-license gate, bundled default voice, clip validation, custom voices, subprocess synth — fully implemented. Real torch install deferred to human UAT.
3. Fish shown-but-disabled GPU gate — the live path on this macOS dev box. NC-license gate present behind GPU gate. D-10 wording reconciled in both REQUIREMENTS.md and ROADMAP.md. Verified live.
4. Fail-fast for uninstalled heavy engines: `heavy_engine_failfast` → `st.error` + `disabled=True` on Convert — fully implemented and AppTest-verified.

The only open items are deferred human UAT (real installs requiring multi-GB downloads or an NVIDIA GPU), following the established Phase-3/4 deferred-UAT precedent. The implementation logic is automated-tested with mocked subprocess; the deferral is intentional and documented in `05-HUMAN-UAT.md`.

---

_Verified: 2026-06-15T22:21:20Z_
_Verifier: Claude (gsd-verifier)_
