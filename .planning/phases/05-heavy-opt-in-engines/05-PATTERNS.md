# Phase 5: Heavy Opt-In Engines - Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 17 new/modified source + 11 new test files
**Analogs found:** 14 with strong in-repo analog / 17 source files (3 worker scripts run out-of-process → RESEARCH templates, not in-repo analogs)

All Diana TTS engines are `Protocol`-typed (not ABC) and register in `diana/tts/registry.py`. The two load-bearing disciplines this phase must mirror exactly:
1. **Lazy heavy import** — torch/llama-cpp/orpheus_cpp/f5_tts/fish are NEVER imported in the app interpreter (ENGINE-01/D-17). They live only in the per-engine venv, reached by `subprocess`. The cheap badge/enumeration path is a pure filesystem probe.
2. **Worker thread never calls `st.*`** — install/download runs on a background thread that writes only to a shared `dl_state` dict; an `@st.fragment` poller renders from the script thread (T-04-SRC / Pitfall 6).

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `diana/tts/orpheus_engine.py` *(new)* | engine (service) | request-response (subprocess synth) | `diana/tts/piper_engine.py` + `native_os_engine.py` + `kokoro_engine.py` | exact (subprocess engine + static VOICES) |
| `diana/tts/f5_engine.py` *(new)* | engine (service) | request-response (subprocess synth) | `piper_engine.py` + `native_os_engine.py` + registry `_piper_voices` merge | exact (subprocess) / role-match (dynamic voices) |
| `diana/tts/fish_engine.py` *(new)* | engine (service) | request-response (subprocess synth) | `f5_engine.py` (sibling) + `gpu_probe.py` gate | exact (clone of F5 + gate) |
| `diana/tts/heavy_install.py` *(new)* | service / provisioner | batch + streaming (subprocess stdout) | `downloads/downloader.py` (`has_space`/`download_file`) + `5_Settings.py` download-thread machinery + `native_os._say_synth` subprocess | role-match (venv-provision itself = new capability) |
| `diana/tts/gpu_probe.py` *(new)* | utility | request-response (subprocess) | `native_os_engine.py::_say_synth` (subprocess discipline) + `install_state.py` (cheap-probe philosophy) | role-match |
| `diana/tts/custom_voices.py` *(new)* | service / model | file-I/O + CRUD | `catalog.py::safe_voice_dest` + `voice_labels.py` + `install_state.py::uninstall_piper_voice` + `downloader.has_space` | role-match |
| `diana/tts/heavy_workers/orpheus_worker.py` *(new)* | utility (out-of-process) | transform (stdin JSON → WAV) | RESEARCH Code Examples §Orpheus worker + `kokoro_engine` `sf.write` | no in-repo analog (runs in venv) |
| `diana/tts/heavy_workers/f5_worker.py` *(new)* | utility (out-of-process) | transform (stdin JSON → WAV) | RESEARCH Code Examples §F5 worker | no in-repo analog |
| `diana/tts/heavy_workers/fish_worker.py` *(new)* | utility (out-of-process) | transform (stdin JSON → WAV) | RESEARCH §F5 worker (mirror) | no in-repo analog |
| `diana/tts/registry.py` *(modified)* | registry / factory | request-response | itself (existing piper/native_os branches) | exact |
| `diana/tts/install_state.py` *(modified)* | utility (probe) | file-I/O (read) | itself (`kokoro_model_installed`/`uninstall_piper_voice`/`voice_in_use`) | exact |
| `diana/paths.py` *(modified)* | config (path resolver) | n/a | itself (`model_dir`/`voices_dir`/`ensure_dirs`) | exact |
| `diana/dashboard/pages/5_Settings.py` *(modified)* | component (UI) | event-driven (button) + streaming (progress) | `_render_kokoro_download_row` + `_import_voice_pair` + `_render_uninstall_control` + dl_state/fragment machinery | exact |
| `diana/dashboard/pages/1_Upload.py` *(modified)* | component (UI) | event-driven | `_engine_readiness` + Convert-button gate | role-match (fail-fast gate is new) |
| `requirements.txt` + `pyproject.toml` *(modified)* | config | n/a | existing pins | exact (bump `streamlit>=1.40.0`) |
| `tests/conftest.py` *(new)* | test (fixtures) | n/a | no shared conftest exists; fixtures modeled on per-test monkeypatch usage | no analog (new shared fixtures) |
| `tests/test_*.py` (heavy_install, gpu_probe, custom_voices, license_gate, orpheus/f5/fish_engine, heavy_failfast, registry_heavy, install_state_heavy) *(new)* | test | n/a | `test_native_os_engine.py` + `test_install_state.py` + `test_tts_registry.py` | exact (mock idioms) |

**No source change needed (reuse verbatim):** `diana/database.py` (`get_setting`/`set_setting` over `app_settings` already generic — license flags + custom-voice metadata are just new keys), `diana/downloads/downloader.py` (`has_space`/`download_file`/`clean_partials` reused as-is for weights), `diana/dashboard/voice_cache.py` (heavy + custom voices already flow through `all_engine_voices`; `clear_voice_cache()` called on install/save).

---

## Pattern Assignments

### `diana/tts/orpheus_engine.py` (engine, request-response) — new

**Analogs:** `diana/tts/piper_engine.py` (subprocess synth + static VOICES), `diana/tts/native_os_engine.py` (subprocess discipline), `diana/tts/kokoro_engine.py` (engine-level model + static VOICES + asset table).

**Class shape + static VOICES** — copy `KokoroEngine` (`kokoro_engine.py:67-127`): `name` class attr, a static `VOICES = [TTSVoice(...)]` list (Orpheus has 8 named voices, Kokoro-style D-19), `list_voices()` returns `list(self.VOICES)`. Imports block (`kokoro_engine.py:1-7`): stdlib + `from diana.tts.base import TTSVoice` only — NO heavy SDK at module top.

**`initialize()` — cheap, no heavy import** — copy the FileNotFoundError-with-actionable-message idiom from `kokoro_engine.py:88-103`; replace the file check with `install_state.heavy_engine_installed("orpheus")`:
```python
def initialize(self):  # cheap: verify the venv+model exist (NO orpheus_cpp import here)
    if not install_state.heavy_engine_installed("orpheus"):
        raise FileNotFoundError(
            "Orpheus not installed — open Settings ▸ Voices and click Install.")
```

**`async synthesize` → out-of-process subprocess** — this is the load-bearing pattern. Mirror `piper_engine.py::_synthesize_binary` (`piper_engine.py:105-131`) and `native_os_engine.py::_say_synth` (`native_os_engine.py:211-233`): `run_in_executor` wrapping a blocking `subprocess.run`, text passed as **data** (stdin JSON), `capture_output=True`, `timeout=...`, read WAV from a temp file, `unlink(missing_ok=True)` in `finally`. Key delta vs piper: invoke the **venv's** python + a worker script, set `HF_HOME` in `env`:
```python
# from native_os_engine.py:199-204 (the run_in_executor wrapper) + piper_engine.py:105-131 (temp WAV + finally unlink)
async def synthesize(self, text, voice="tara", speed=1.0) -> bytes:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self._subprocess_synth, text, voice, speed)
# vpy = paths.venvs_dir()/"orpheus"/("Scripts/python.exe" if win else "bin/python")
# req = json.dumps({"text": text, "voice_id": voice, "out": tmp})  # text = data, never shell
# subprocess.run([str(vpy), str(worker)], input=req, text=True, capture_output=True,
#                timeout=600, env={**os.environ, "HF_HOME": str(paths.hf_cache_dir())})
```
Security: `shell=False` implicit (list argv), text as stdin — the exact T-03-06 precedent in `native_os_engine.py:216-225`.

**Engine-level asset/model metadata** — if exposing the GGUF download record (D-04 footprint confirm), mirror `kokoro_engine.py:15-65` (`KOKORO_MODEL_VARIANTS` dict + `kokoro_download_assets()`): a static table of `{filename, url|repo, size_bytes, label}` so the Settings row builds the install without hardcoding repo IDs in the page.

---

### `diana/tts/f5_engine.py` (engine, request-response) — new

**Analogs:** `piper_engine.py` + `native_os_engine.py` (subprocess), and `registry.py::_piper_voices` (`registry.py:85-110`) for the **dynamic** voice list (bundled default + saved custom voices, vs Orpheus's static list).

**Subprocess synth** — same as Orpheus above, but the worker request carries `ref_file`, `ref_text`, `gen_text` (RESEARCH F5 worker example) into the **torch** venv. Reuse the `_subprocess_synth` shape verbatim.

**Dynamic `list_voices()`** — F5 has no baked-in voices (zero-shot clone); it surfaces the bundled default (D-15) + saved custom voices (D-14). Mirror the merge in `registry.py::_piper_voices` (`registry.py:99-110`): start from a static `[bundled_default]`, append each saved custom voice (from `custom_voices.list_custom_voices("f5")`), dedupe by id. Keep it import-light (no torch) — `custom_voices` is a filesystem/`app_settings` read.

---

### `diana/tts/fish_engine.py` (engine, request-response) — new

**Analog:** `f5_engine.py` (sibling, shares the torch venv + dynamic clone voices) + `gpu_probe.py`.

Clone the F5 engine. Delta: `initialize()` gates on BOTH `install_state.heavy_engine_installed("fish")` AND `gpu_probe.capable_nvidia_gpu()` (D-10) before allowing synth. Per RESEARCH assumption A6, treat Fish as zero-shot clone (reuse Custom Voices + a bundled default) unless plan-time verification shows preset named voices — in which case `list_voices()` becomes static like Orpheus.

---

### `diana/tts/heavy_install.py` (service / provisioner, batch+streaming) — new

**Analogs:** `downloads/downloader.py` (`has_space`/`download_file`/`clean_partials`), `5_Settings.py` download-thread machinery (`_download_piper_voice`/`_new_dl_state`/`_download_action`), `native_os_engine.py::_say_synth` (subprocess streaming).

**`has_space` pre-check before any byte** — reuse `downloader.has_space` verbatim (`downloader.py:87-97`); it ancestor-walks a not-yet-created dir, so it works on a fresh `venvs_dir()`. Call site pattern is `5_Settings.py:697-703`.

**Phase A — `uv` subprocess provisioner (NEW CAPABILITY, no exact analog):** the venv-creation/pip-install orchestration is genuinely new (Phase 4 only downloaded files). The *subprocess streaming* shape, however, copies `native_os_engine.py:226-231` (list argv, `shell=False`, no text interpolation) extended to `subprocess.Popen(..., stdout=PIPE, stderr=STDOUT)` streaming lines (RESEARCH Pattern 1):
```python
# RESEARCH Pattern 1 — drive the bundled uv binary, stream stdout into on_line→dl_state
proc = subprocess.Popen([uv, "pip", "install", "--python", str(vpy), *packages],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
for line in proc.stdout:
    if on_line: on_line(line.rstrip())   # writes dl_state["step"]; @st.fragment renders
if proc.wait() != 0: raise RuntimeError("install step failed")
```
`uv` path comes from `paths.uv_binary()` (new), NOT PATH. The marker file written on success (`paths.venvs_dir()/f".{engine}.installed"`) is what `install_state.heavy_engine_installed` probes.

**Phase B — weights** — reuse `download_file` (`downloader.py:34-84`) for single-URL+md5 assets; per RESEARCH Q-C use `huggingface_hub` (inside the venv subprocess, `HF_HOME=hf_cache_dir()`) for multi-file repos, gated by `has_space` first. Either way progress lands in `dl_state` (Phase-4 shape).

**Two-phase progress record** — extend `_new_dl_state` (`5_Settings.py:133-145`) with a `phase`/`step` field. Background thread writes only the dict; never `st.*` (the `_download_piper_voice` discipline, `5_Settings.py:87-131`).

---

### `diana/tts/gpu_probe.py` (utility, request-response) — new

**Analogs:** `native_os_engine.py::_say_synth` (subprocess discipline: list argv, `capture_output`, `timeout`), `install_state.py` (the "resolve a capability cheaply, NO heavy import" philosophy + module docstring tone).

Pure module: `shutil.which("nvidia-smi")` + `subprocess.run([smi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)`, parse VRAM, return `(ok, vram_gb, reason)` (RESEARCH Pattern 4). MUST NOT import torch (Pitfall 4 — no `torch.cuda.is_available()` on the badge path). `FISH_MIN_VRAM_GB = 12` module constant (SCREAMING_SNAKE_CASE, per conventions).

---

### `diana/tts/custom_voices.py` (service / model, file-I/O + CRUD) — new

**Analogs:** `catalog.py::safe_voice_dest` (`catalog.py:159-188`, path safety), `voice_labels.py` (`app_settings`-backed metadata), `install_state.py::uninstall_piper_voice` (`install_state.py:98-116`, scoped delete + freed bytes), `downloader.has_space`.

**Clip-file path safety (D-13/V12)** — copy `catalog.safe_voice_dest` structure exactly (`catalog.py:179-188`): `os.path.basename` → extension allow-list (here `.wav`/`.mp3`/`.txt` instead of `.onnx`) → resolved-prefix containment check under `paths.custom_voices_dir()` (new). Raise `ValueError` on bad ext / traversal.

**Clip validation (D-13)** — pure, Streamlit-free, returns `(ok, message)` like `_import_voice_pair` (`5_Settings.py:475-517`): use `soundfile.info()` (already a dep) for duration/samplerate (RESEARCH Don't Hand-Roll), reject empty transcript, accept ~2–12 s, don't reject sub-24 kHz (16 kHz `st.audio_input` default — Pitfall 5/7). Never raise to the UI.

**Metadata storage (D-14)** — mirror `voice_labels.py:41-82`: namespaced JSON-valued `app_settings` key (e.g. `voice.custom.f5.<id>` → `{name, ref_file, ref_text, ...}`) via `set_setting`/`get_setting` (lazy-imported, `database.py:148-167`). `get_*` tolerates malformed JSON → `{}` (the T-04-LBLJSON idiom, `voice_labels.py:60-68`).

**Save/remove** — write clip+transcript under `custom_voices_dir()`; removal mirrors `install_state.uninstall_piper_voice` (`install_state.py:98-116`): scoped to the per-user dir, `unlink(missing_ok=True)`, return freed bytes. Removable like any voice (D-14) → reuse `voice_in_use` block (`install_state.py:66-95`).

---

### `diana/tts/heavy_workers/{orpheus,f5,fish}_worker.py` (utility, transform) — new, NO in-repo analog

These run under the **venv's** python (package-data, NOT frozen-imported), so they import torch/llama-cpp/orpheus_cpp freely — the one place heavy SDKs are allowed. Templates are in RESEARCH §Code Examples (orpheus_worker / f5_worker, VERIFIED). Shape: read JSON from `sys.stdin`, run inference, `sf.write(out, audio, sr, format="WAV")` (the `sf.write` call mirrors `kokoro_engine.py:118-120`). Keep them tiny and dependency-isolated. (Likely no `__init__.py` — they are invoked by path, not imported by the app; confirm at plan time whether packaging treats the dir as package-data.)

---

### `diana/tts/registry.py` (registry / factory) — modified

**Analog:** itself. Add `orpheus`/`f5`/`fish` across the same four seams the existing engines use:

- **`_ASCII_ONLY_ENGINES`** (`registry.py:14-18`) — add `"orpheus": False, "f5": False, "fish": False` (neural → UTF-8 capable).
- **`list_engines()`** (`registry.py:194-196`) — append the three heavy names (they badge/gate cheaply).
- **`_get_engine_class`** (`registry.py:21-31`) — add lazy-import branches exactly like the existing `piper`/`native_os` ones:
```python
if engine_name == "orpheus":
    from diana.tts.orpheus_engine import OrpheusEngine; return OrpheusEngine
```
- **`create_engine`** (`registry.py:34-53`) — add `elif engine_name == "orpheus": ...` constructing the heavy engine (no config model paths needed — they self-locate via `paths`).
- **`get_engine_voices`** (`registry.py:56-82`) — Orpheus uses the static-`VOICES` default branch; F5/Fish need a dynamic branch like the `piper`/`native_os` special-cases (return `cls.VOICES` + saved custom voices, import-light).

All heavy imports stay INSIDE the branch functions (the existing lazy pattern) so `all_engine_voices`/`engine_is_ascii_only` never pull torch.

---

### `diana/tts/install_state.py` (utility probe) — modified

**Analog:** itself. Add filesystem-only probes alongside the Kokoro/Piper ones (`install_state.py:23-64`), keeping the module's NO-heavy-import contract (its whole docstring, `install_state.py:1-13`):
```python
def heavy_engine_installed(engine: str) -> bool:   # RESEARCH install-state example
    venv = paths.venvs_dir() / ("orpheus" if engine == "orpheus" else "torch")
    py = venv / ("Scripts/python.exe" if _is_win() else "bin/python")
    marker = paths.venvs_dir() / f".{engine}.installed"
    return py.exists() and marker.exists()
```
Add `heavy_footprint_bytes(engine)` (sum venv + weight sizes, like `piper_footprint_bytes:48-56`), heavy-engine uninstall (mirror `uninstall_piper_voice:98-116` — scoped rmtree of the venv + cache, return freed bytes), and reuse `voice_in_use` (`install_state.py:66-95`) for the heavy/custom-voice uninstall block.

---

### `diana/paths.py` (config / path resolver) — modified

**Analog:** itself (`paths.py:41-57`). Add `venvs_dir()`, `custom_voices_dir()`, `hf_cache_dir()`, `uv_binary()` as one-line `data_dir() / "..."` returns mirroring `model_dir`/`voices_dir`, and add the new dirs to the `ensure_dirs()` tuple (`paths.py:53-57`). `uv_binary()` resolves the bundled `data/bin/uv-{macos,windows}` (Phase 6 packages it; Phase 5 needs a dev-resolved path).

---

### `diana/dashboard/pages/5_Settings.py` (component, event-driven + streaming) — modified

**Analogs:** `_render_kokoro_download_row` (the engine-level install row), `_import_voice_pair`/`_import_voice_from_path` (Custom Voices upload), `_render_uninstall_control` (uninstall), the dl_state/thread/fragment machinery, `_cross_engine_badge`.

**Heavy-engine install rows** — copy `_render_kokoro_download_row` (`5_Settings.py:619-707`) almost verbatim, placed under the "Engine models" section (`5_Settings.py:1429-1436`). It already demonstrates EVERY required piece:
- D-05 disk pre-check: `ok, free = has_space(paths.model_dir(), _footprint)` then refuse (`5_Settings.py:696-703`) — point at `venvs_dir()`.
- D-04 footprint confirm before large download (`5_Settings.py:681-692`) — itemize deps vs model (e.g. "torch 2.4 GB + model 1.1 GB").
- threaded start guarded by `_can_spawn_download` (`5_Settings.py:355-372`).
- progress via `_render_download_progress(_KEY)` fragment (`5_Settings.py:644-668`).
- Installed/Cancel/Cancelling/Resume action column driven by pure `_download_action` (`5_Settings.py:646-663`).

The thread target is the NEW `heavy_install` two-phase function instead of `_download_kokoro_model` (`5_Settings.py:315-352`), but the `dl_state`/`_new_dl_state`/`@st.fragment`/`threading.Thread(..., daemon=True)` scaffolding is reused unchanged.

**License gate (D-08)** — before the install button for F5/Fish, a blocking "I accept" persisted in `app_settings`. Model on the durable-pref read/write already in this page: `get_setting(...)=="1"` check + `set_setting(...,"1")` on accept + `st.rerun()` — exactly the dismissible-hint idiom in `1_Upload.py:224-235`.

**GPU gate (D-10)** — Fish row calls `gpu_probe.capable_nvidia_gpu()`; if not ok, render the row **shown-but-disabled** with the reason string (e.g. `st.button("Install", disabled=True)` + `st.caption(reason)`), mirroring the disabled "Installed" button at `5_Settings.py:651`.

**Custom Voices section (D-11)** — new subsection under the Voices tab, modeled on the "Import a voice" section (`5_Settings.py:1538-1576`):
- Upload path: `st.file_uploader` (mp3 + txt) → validate via `custom_voices.validate_clip` (the `_import_voice_pair` `(ok,msg)` + `clear_voice_cache()` + `st.success/st.error` pattern, `5_Settings.py:1555-1561`).
- Capture path: `st.audio_input(...)` (NEW widget, requires `streamlit>=1.40`) + `st.text_area` transcript → same validate/save.
- Saved custom voices list with the two-step uninstall (`_render_uninstall_control`, `5_Settings.py:568-616`) and per-voice label edit (already flows through the cross-engine browser + `_render_label_editor`).

**Cross-engine badge (D-11)** — extend `_cross_engine_badge` (`5_Settings.py:833-863`) with `orpheus`/`f5`/`fish` branches calling `install_state.heavy_engine_installed`/`heavy_footprint_bytes` (cheap, no heavy import — the existing `kokoro`/`piper` branch shape).

---

### `diana/dashboard/pages/1_Upload.py` (component, event-driven) — modified

**Analog:** `_engine_readiness` (`1_Upload.py:43-82`) + the Convert-button block (`1_Upload.py:364-388`).

**Footprint/readiness badge** — extend `_engine_readiness` with `orpheus`/`f5`/`fish` branches returning `(ready, note)` from `install_state.heavy_engine_installed` (filesystem probe only — the existing `kokoro`/`piper` shape, `1_Upload.py:56-82`). Fish badge also surfaces the GPU-gate reason.

**Fail-fast (D-16 — NEW behavior, no exact analog)** — today the Convert button is NOT gated on readiness (`1_Upload.py:364-388`). Add: when the selected engine is a heavy engine and `not heavy_engine_installed`, show an actionable `st.error("Orpheus isn't installed — install it in Settings ▸ Voices")` and `disabled=True` on Convert (or block job creation), so it **never errors mid-job**. The readiness probe is already cheap and in hand; this just wires it to the button-disable + a clear message (the `resolve_default_voice` stale-id backstop at `1_Upload.py:185-187` remains the selection-time complement).

---

## Shared Patterns

### Lazy heavy import (ENGINE-01 / D-17)
**Sources:** `kokoro_engine.py:1-7,105-106` (SDK imported INSIDE `initialize`), `piper_engine.py:58-59,84` (`import piper` inside the method), `registry.py:21-31` (engine classes lazy-imported per branch).
**Apply to:** all heavy engines + registry + install_state + custom_voices. The torch/llama-cpp/orpheus_cpp/f5_tts SDKs appear ONLY in `heavy_workers/*` (run by the venv python). Tests assert this (`test_registry_heavy.py`, `test_install_state_heavy.py`) by checking the heavy module name is absent from `sys.modules` after a cheap-path call.

### Out-of-process subprocess synthesis (text as data, never shell)
**Sources:** `native_os_engine.py:211-233` (`_say_synth`: list argv, `shell=False`, text as final argv/stdin, temp WAV `unlink(missing_ok=True)` in `finally`, `capture_output=True`, `timeout`), `piper_engine.py:105-131` (`_synthesize_binary`: same shape with stdin text + `run_in_executor`).
**Apply to:** all three heavy engines' `_subprocess_synth`; the `uv` driver in `heavy_install.py`; `gpu_probe.py`.
```python
# native_os_engine.py:226-231 — the discipline to copy
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
if proc.returncode != 0:
    raise RuntimeError(f"say failed: {proc.stderr.strip()}")
return Path(tmp_path).read_bytes()
```

### Background-thread download/install → `dl_state` → `@st.fragment` (worker never calls `st.*`)
**Source:** `5_Settings.py:87-131` (`_download_piper_voice` thread target writes only `state`), `:133-145` (`_new_dl_state` record), `:148-194` (pure `_download_action`/`_can_spawn_download` — unit-testable, no ScriptRunContext), `:197-264` (`@st.fragment(run_every="0.5s")` poller, the only place `st.*` runs), `:267-288`/`:355-372` (`threading.Thread(..., daemon=True)` start guarded by `_can_spawn_download`).
**Apply to:** every heavy install row (Phase A uv stream + Phase B weights), the Custom Voices save if it ever downloads. Extend `_new_dl_state` with a `phase`/`step` field for the two-phase progress (RESEARCH Pattern 3).

### Disk pre-check before any byte (D-04/D-05)
**Source:** `downloader.py:87-97` (`has_space`, ancestor-walks a not-yet-created dir), call site `5_Settings.py:696-703` (refuse with a clear "need X MB, only Y free" message).
**Apply to:** every heavy install (point at `venvs_dir()`/`hf_cache_dir()`); the itemized deps-vs-model confirm (D-04) extends `5_Settings.py:681-692`.

### Durable UI-only prefs via `app_settings` (no file editing)
**Source:** `database.py:148-167` (`get_setting`/`set_setting`, `ON CONFLICT` upsert over a `key TEXT PRIMARY KEY` table, schema `database.py:41-44`), `voice_labels.py:41-82` (namespaced JSON-valued key + malformed-tolerant read), `1_Upload.py:224-235` (dismissible-hint accept-once idiom).
**Apply to:** license-accepted flags (D-08, e.g. `license.accepted.f5`), custom-voice metadata (D-14), the per-engine default-voice memory already used. No schema change needed.

### Path safety for untrusted uploads (basename + ext allow-list + containment)
**Source:** `catalog.py:159-188` (`safe_voice_dest`), reuse path in `5_Settings.py:506,546`.
**Apply to:** `custom_voices.py` clip/transcript landing (allow-list `.wav`/`.mp3`/`.txt`, contain under `custom_voices_dir()`).

### Cheap install-state / footprint probe (filesystem only, NO SDK)
**Source:** whole `install_state.py` (docstring `:1-13`; `kokoro_model_installed:59-63`; `piper_footprint_bytes:48-56`; `uninstall_piper_voice:98-116`; `voice_in_use:66-95`).
**Apply to:** `heavy_engine_installed`/`heavy_footprint_bytes`/heavy-uninstall, the Upload + Settings badges, and the fail-fast gate.

### Two-step destructive confirm + freed-bytes + cache clear
**Source:** `5_Settings.py:568-616` (`_render_uninstall_control`: in-use block via `voice_in_use` → per-key `st.session_state` confirm flag → freed-MB caption → confirm/cancel → `clear_voice_cache()` + `st.rerun()`).
**Apply to:** heavy-engine uninstall and custom-voice removal.

### Engine readiness → actionable message (fail-fast scaffold)
**Source:** `1_Upload.py:43-82` (`_engine_readiness` returns `(ready, note)` from `install_state`, no heavy import), `kokoro_engine.py:92-103` (`initialize` raises FileNotFoundError naming "Settings ▸ Voices").
**Apply to:** D-16 fail-fast on Upload (disable Convert + clear prompt for uninstalled heavy engine).

---

## No Analog Found

| File | Role | Data Flow | Reason / Source to use instead |
|------|------|-----------|--------------------------------|
| `diana/tts/heavy_install.py` (the `uv venv`/`uv pip install` orchestration itself) | provisioner | batch | Phase 4 only downloaded files; provisioning a Python env is the genuinely new capability. Use RESEARCH Pattern 1 (`provision_venv`). The *threading/progress/has_space* wrapper around it IS analogged (download machinery above). |
| `diana/tts/heavy_workers/orpheus_worker.py` | out-of-process script | transform | Imports orpheus_cpp; runs in the venv, not the app. Template: RESEARCH §Code Examples (Orpheus worker, VERIFIED). `sf.write` mirrors `kokoro_engine.py:118-120`. |
| `diana/tts/heavy_workers/f5_worker.py` | out-of-process script | transform | Imports f5_tts; venv-only. Template: RESEARCH §Code Examples (F5 worker, VERIFIED). |
| `diana/tts/heavy_workers/fish_worker.py` | out-of-process script | transform | Imports fish_speech; venv-only. Mirror f5_worker; inference signature verified at plan time (RESEARCH Q-D / A6). |
| `tests/conftest.py` | test fixtures | n/a | No shared conftest exists today (tests monkeypatch inline). New shared fixtures: fake venv dir, mock `subprocess.run`/`Popen`, fake `nvidia-smi` output, temp clip files (RESEARCH Wave 0 Gaps). |
| `1_Upload.py` fail-fast gate (D-16) | UI behavior | event-driven | Convert button is currently ungated; the disable-on-uninstalled behavior is new. Wires the existing cheap readiness probe to the existing button-disable mechanism (`1_Upload.py:364-368`). |

---

## Metadata

**Analog search scope:** `diana/tts/` (base, registry, install_state, kokoro_engine, piper_engine, native_os_engine, voice_labels, catalog), `diana/downloads/downloader.py`, `diana/paths.py`, `diana/database.py`, `diana/dashboard/pages/{1_Upload,5_Settings}.py`, `diana/dashboard/voice_cache.py`, `tests/` (test_native_os_engine, test_install_state, test_tts_registry), `pyproject.toml`, `requirements.txt`.
**Files scanned:** ~20 source files read in full or by targeted range; 3 test files + project config inspected for mock/pin idioms.

**Test mock idioms (for the Wave 0 test files):**
- Subprocess mock: `patch("diana.tts.<module>.subprocess.run", side_effect=_fake_run)` returning `MagicMock(returncode=0, stderr="")` — `test_native_os_engine.py:122-124`.
- Absent/fake SDK injection: `patch.dict(sys.modules, {...})` — `test_native_os_engine.py:199-208`.
- Filesystem probe: `monkeypatch.setattr("diana.paths.model_dir", lambda: tmp_path)` then touch fake files — `test_install_state.py:66-89`. Extend with `paths.venvs_dir`/`paths.hf_cache_dir`.
- Registry assertions: `_ASCII_ONLY_ENGINES`, `list_engines()`, dynamic voices — `test_tts_registry.py:20-67`.
- pytest config: `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed), `testpaths=["tests"]`, default `-m 'not network'`, `network` marker (`pyproject.toml:58-64`). Quick run: `/Users/tyler/Repos/diana/.venv/bin/python -m pytest tests/test_<touched>.py -x -q`.

**Config bump (Pitfall 5):** `streamlit>=1.30.0` → `>=1.40.0` in BOTH `pyproject.toml:13` and `requirements.txt:2` (required for `st.audio_input`, D-11; not used anywhere today).

**Pattern extraction date:** 2026-06-15
