# Phase 4: Engine Management & Voice Catalog - Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 19 (5 new modules + 2 bundled data assets + 5 modified + 7 Wave-0 test files)
**Analogs found:** 19 / 19 (every file maps to a real in-repo analog)

> Diana has no formatter/ABC inheritance — engines are structural `Protocol`s, helpers are module-level functions, durable prefs live in `app_settings`. All pure logic stays Streamlit-free and unit-testable; all heavy SDK imports are lazy/inside-function. Every new pure module copies the `native_voices_macos.py` / `native_os_engine.py` "pure helpers + thin I/O wrapper" shape. All pytest runs use `.venv` (user memory).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `diana/downloads/__init__.py` | package marker | — | `diana/tts/__init__.py` (empty) | exact |
| `diana/downloads/downloader.py` | service (NEW) | streaming / file-I/O | `diana/tts/native_voices_macos.py` (pure fn + thin I/O wrapper) + `diana/database.py:delete_job` (file cleanup) | role-match |
| `diana/tts/catalog.py` | service / transform (NEW) | transform (JSON→TTSVoice) + file-I/O (bundled JSON read) | `diana/tts/native_voices_macos.py` (parse text→`list[TTSVoice]`) | exact |
| `diana/tts/voice_labels.py` *(or fold into registry)* | service / persistence (NEW) | CRUD (app_settings) + transform | `diana/tts/registry.py:resolve_default_voice` (db wrapper over pure helper) + `database.py:get_setting/set_setting` | exact |
| `diana/tts/install_state.py` *(or fold into registry)* | utility (NEW) | file-I/O probe | `diana/tts/registry.py:engine_is_ascii_only` (cheap no-import map) + `paths.py` probes | exact |
| `diana/data/piper_voices_curated.json` | config / data fixture (NEW) | static data | `tests/fixtures/say_voices.txt` (bundled snapshot used by parser) | role-match |
| `diana/data/samples/*.mp3` | data asset (NEW) | static binary | (no in-repo binary-asset analog) | none — see No Analog |
| `diana/tts/registry.py` | registry (MODIFY) | request-response (factory) | itself — extend existing `get_engine_voices`/`resolve_default_voice` pattern | exact |
| `diana/tts/kokoro_engine.py` | engine (MODIFY) | file-I/O (model path) | itself + `piper_engine.py` `_resolve_model_path`; route the `initialize()` wget-hint through `downloads/` | exact |
| `diana/tts/piper_engine.py` | engine (likely NO change) | file-I/O (model path) | itself — `_resolve_model_path` already resolves `{voice}.onnx` in `model_dir` | exact |
| `diana/dashboard/pages/5_Settings.py` | component / UI (MODIFY) | event-driven (Streamlit) | itself + `1_Upload.py` picker block (lines 109-176) | exact |
| `diana/dashboard/pages/1_Upload.py` | component / UI (MODIFY) | event-driven (Streamlit) | itself — engine `selectbox` at line 102-107 (add badges) | exact |
| `tests/test_downloader.py` | test (NEW) | unit (tmp_path) | `tests/test_piper_engine.py` (mock-SDK, tmp_path fixtures) | role-match |
| `tests/test_downloader_net.py` | test (NEW, `@pytest.mark.network`) | integration (network) | `tests/test_native_os_engine.py::test_macos_real_synth_smoke` (real-resource skip-gated smoke) | role-match |
| `tests/test_catalog.py` | test (NEW) | unit (fixture parse) | `tests/test_native_voices_macos.py` (fixture→parser, guarded import) | exact |
| `tests/test_install_state.py` | test (NEW) | unit (tmp_path) | `tests/test_tts_registry.py` (cheap-probe assertions) + `test_piper_engine.py` tmp_path | role-match |
| `tests/test_voice_import.py` | test (NEW) | unit | `tests/test_native_os_engine.py` (pure-helper, guarded import) | role-match |
| `tests/test_voice_labels.py` | test (NEW) | unit | `tests/test_native_os_engine.py::test_default_voice_validation` (mock `get_setting`) | exact |
| `tests/test_uninstall.py` | test (NEW) | unit (tmp_path + in-mem db) | `tests/test_database.py` + `test_piper_engine.py` tmp_path | role-match |

---

## Pattern Assignments

### `diana/downloads/downloader.py` (service, streaming/file-I/O) — NEW

**Analogs:** `diana/tts/native_voices_macos.py` (the "one pure helper + one thin I/O wrapper, module-level functions, no class needed" shape) and `diana/database.py:delete_job` (lines 248-271, the `Path(...).unlink(missing_ok=True)` cleanup idiom). RESEARCH Patterns 1+2 give the verified download/disk-check bodies — copy them; this section gives the *house style* to wrap them in.

**Module shape to mirror** — no class, module-level functions, `logger = logging.getLogger(__name__)`, prose docstring at top explaining the non-obvious logic (`native_voices_macos.py:1-16`):
```python
"""Generic, engine-agnostic resumable download/cache layer.

stdlib + requests only — NO piper/kokoro/onnx import (D-19: reused by Piper voices
+ Kokoro model now, heavy engines in Phase 5). Resume via HTTP Range -> .part ->
md5 verify -> atomic os.replace. Disk-space pre-check gates every download (D-05).
"""
import hashlib, logging, os, shutil
from pathlib import Path
import requests

logger = logging.getLogger(__name__)
```

**Core download pattern:** copy RESEARCH Pattern 1 verbatim (`04-RESEARCH.md:224-270`) — `download_file(url, dest, expected_md5, expected_size, progress, cancel)`, `.part` append-on-206 / reset-on-200, md5 verify, `os.replace`. The `Content-Range`-as-truth and `iter_content(chunk_size=1<<16)` details are load-bearing (Pitfalls 1+2).

**Disk-check pattern:** copy RESEARCH Pattern 2 verbatim (`04-RESEARCH.md:281-287`) — `has_space(target, needed_bytes, margin=1.10)` with the ancestor-walk for a not-yet-created `model_dir()`.

**Cancel/cleanup idiom** (mirror `database.py:259` `unlink(missing_ok=True)`): on md5 mismatch `part.unlink(missing_ok=True)` then `raise ValueError(...)`; on cancel, leave `.part` for Resume (D-06/D-07). Partial-cleanup glob for VOICE-07/D-18: `for p in paths.model_dir().glob("*.part"): p.unlink(missing_ok=True)`.

**Error-handling house style** (typed exception + f-string, matching `piper_engine.py:52-55`): `raise ValueError(f"md5 mismatch for {dest.name}: {actual} != {expected_md5}")`. The downloader raises; the UI catches and renders (never the reverse).

**Hard constraint:** keep this module import-clean of `piper`/`kokoro`/`streamlit` — exactly how `native_os_engine.py` keeps `winrt`/`streamlit` off module-top (`native_os_engine.py:1-16`). It is consumed by both engines and by the UI thread (RESEARCH Pattern 3) but imports neither.

---

### `diana/tts/catalog.py` (transform + file-I/O) — NEW

**Analog:** `diana/tts/native_voices_macos.py` — this is the textbook match. That module does `parse_say_voices(text) -> list[TTSVoice]` (pure, fixture-testable) + `enumerate_macos_voices()` (thin subprocess wrapper). `catalog.py` does the same: `parse_manifest(json_text_or_dict) -> list[TTSVoice]` (pure) + `load_bundled_manifest()` / `refresh_catalog()` (thin file/network wrappers).

**Pure-parse pattern to mirror** (`native_voices_macos.py:52-77` — best-effort, skip-malformed, build `TTSVoice`):
```python
def parse_say_voices(text: str) -> list[TTSVoice]:
    voices: list[TTSVoice] = []
    for line in text.splitlines():
        ...
        voices.append(TTSVoice(
            id=name, name=name, language=locale, gender="unknown",
            tier=_tier_for(base), bilingual=False,
        ))
    return voices
```
For `catalog.py`, the per-entry build maps the verified manifest schema (`04-RESEARCH.md:452-481`) → `TTSVoice`: `id=key`, `name`→display, `language["code"].replace("_","-").lower()` (the exact `en_US -> en-us` fold done at `native_voices_macos.py:67`), `quality`→`tier`, plus footprint = sum of `files[*.onnx].size_bytes + [*.onnx.json].size_bytes` and the download URL `f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{path}"` (`04-RESEARCH.md:490`). Skip-malformed-entry, never crash — mirror the `if not m: continue` discipline.

**Curated-vs-show-all + group-by-language (D-01/D-03):** pure list operations over the parsed `list[TTSVoice]`, mirroring `1_Upload.py:42-51` `_system_language_first` (group by `(v.language or "").strip().lower()`). Reuse Phase-3 `filter_voices`/`order_by_quality` from `native_os_engine.py` verbatim (D-03 — see Shared Patterns).

**Tier-prelabel constant pattern** (if curation needs a curated-set membership set): copy the module-constant style at `native_voices_macos.py:35-49` (`_NOVELTY`/`_ENHANCED` frozenset-like sets + a `_tier_for(base)` classifier).

**Refresh wrapper** (the only network touch; mirror `enumerate_macos_voices`'s thin wrapper at `native_voices_macos.py:80-92`): `requests.get(MANIFEST_URL, timeout=...)` → `parse_manifest(r.json())`; failures degrade to the bundled snapshot (D-02), logged with `logger.warning(...)` (`%`-style, never f-string, per CLAUDE.md Logging).

---

### `diana/tts/voice_labels.py` (persistence + transform) — NEW *(planner may fold into registry.py)*

**Analog:** `diana/tts/registry.py:resolve_default_voice` (lines 76-100) — the canonical "db-aware wrapper that reads `app_settings`, delegates the pure part to a Streamlit-free helper, and lazy-imports `get_setting`" pattern. Copy its structure exactly.

**The wrapper pattern** (`registry.py:96-100`):
```python
def resolve_default_voice(db_path, engine_name, voices, engine_default) -> str:
    from diana.database import get_setting          # lazy — keeps DB dep off module import
    from diana.tts.native_os_engine import resolve_default_voice as _resolve_pure
    remembered = get_setting(db_path, f"tts.default_voice.{engine_name}", None) or ""
    return _resolve_pure(remembered, voices, engine_default)
```

**Storage shape (D-14):** copy RESEARCH's recommended shape verbatim (`04-RESEARCH.md:528-549`) — one JSON-valued `app_settings` key per voice id: `key = f"voice.labels.{engine}.{voice_id}"`, value = `json.dumps({...})`. `get_label_overrides` / `set_label_overrides` wrap `get_setting`/`set_setting` (`database.py:148-167`). `apply_overrides(voice, overrides)` uses `dataclasses.replace(voice, **merged)` so the result stays a plain `TTSVoice` the Phase-3 filters already honor.

**`set_setting` upsert it calls** (`database.py:158-167`) — already idempotent (`ON CONFLICT ... DO UPDATE`); no new DB code needed.

**Pure merge is unit-testable; the read is mocked in tests** (mirror `test_native_os_engine.py:250` `patch("diana.database.get_setting", return_value=...)`).

---

### `diana/tts/install_state.py` (utility, file-I/O probe) — NEW *(planner may fold into registry.py)*

**Analog:** `diana/tts/registry.py:engine_is_ascii_only` (lines 118-126) — the explicit "cheap, NO engine import" lane. ENGINE-01 forbids importing onnxruntime/piper just to show a badge; this probe mirrors that constraint.

**Probe pattern:** copy RESEARCH Pattern 4 verbatim (`04-RESEARCH.md:341-353`):
```python
from diana import paths
def piper_voice_installed(voice_id: str) -> bool:
    return (paths.model_dir() / f"{voice_id}.onnx").exists()
def kokoro_model_installed() -> bool:
    md = paths.model_dir()
    onnx = any((md / n).exists() for n in
               ("kokoro-v1.0.onnx", "kokoro-v1.0.fp16.onnx", "kokoro-v1.0.int8.onnx"))
    return onnx and (md / "voices-v1.0.bin").exists()
```
These filenames match `config.py:32-38` (`kokoro-v1.0.onnx`, `voices-v1.0.bin`, `en_US-lessac-medium.onnx`) and `piper_engine._resolve_model_path` (`piper_engine.py:44` — `{voice}.onnx` in `model_dir`). Footprint when not installed reads from the catalog manifest `size_bytes` (not the filesystem). `paths.model_dir()` is at `paths.py:41-46`.

---

### `diana/tts/registry.py` (registry, MODIFY)

**Analog:** itself — extend the existing patterns, do not invent new ones.

**Cross-engine aggregation (D-10)** builds on the existing `get_engine_voices` (lines 56-73) + `list_engines` (lines 113-115). The aggregation is: `for e in list_engines(): for v in get_engine_voices(e, config): ...` tagging each with its engine. Mirror the existing native_os special-case branch (lines 64-71) — native_os constructs/initializes/shuts-down a short-lived engine; kokoro/piper return static `cls.VOICES`.

**Install-state helpers** plug in alongside `engine_is_ascii_only` (the cheap-no-import map at lines 118-126) — same lane. If `install_state.py` is a separate module, `registry.py` may re-expose thin shims; the constraint (RESEARCH `04-RESEARCH.md:217`) is that the cheap-probe logic stays Streamlit-free and import-light.

**Do NOT touch** `create_engine` (lines 34-53) wiring beyond what Kokoro-download needs.

---

### `diana/tts/kokoro_engine.py` (engine, MODIFY — D-19)

**Analog:** itself + `piper_engine.py`. D-19 replaces the `wget`-hint `FileNotFoundError` (lines 35-46) with an in-UI download via `downloads/`. The download itself is **UI-triggered** (ENGINE-04) — the engine's `initialize()` still raises if files are absent (the UI downloads them *before* synth, then `create_engine` succeeds).

**Current hint to replace** (`kokoro_engine.py:35-40`):
```python
if not model.exists():
    raise FileNotFoundError(
        f"Kokoro model not found at {model}. Download it with:\n"
        f'  wget -P "{model.parent}" https://github.com/.../kokoro-v1.0.onnx'
    )
```
The Kokoro asset URLs are verified (`04-RESEARCH.md:497-501`). Kokoro maps to an **engine-level "model installed?" badge** (single model, many baked-in voices — D-19/discretion), not per-voice rows. Minimal-change principle: the engine class barely changes; the new behavior lives in the Voices-tab UI + `downloads/` + `install_state.kokoro_model_installed`.

---

### `diana/tts/piper_engine.py` (engine, likely NO change)

**Analog:** itself. `_resolve_model_path` (lines 38-47) already resolves `{voice}.onnx` in `model_dir` and falls back to the default — so a downloaded/imported voice file becomes selectable with **zero engine edits** (RESEARCH "Voice file resolution at synth time", `04-RESEARCH.md:95`). `PiperVoice.load` auto-loads the sibling `.onnx.json` (`piper_engine.py:92`; convention verified). The phase lands files next to each other; the engine needs no change. Flag for planner: confirm no edit needed before assigning a task.

---

### `diana/dashboard/pages/5_Settings.py` (UI, MODIFY — D-09 the management hub)

**Analog:** itself + the `1_Upload.py` picker block. The page is restructured into `st.tabs` (D-09) with a Voices tab.

**Tabs restructure** — copy RESEARCH's snippet (`04-RESEARCH.md:516-525`):
```python
tab_general, tab_voices, tab_processing, tab_llm, tab_news = st.tabs(
    ["General", "Voices", "Processing", "LLM Cleaning", "News"]
)
with tab_voices:
    ...   # cross-engine browser (D-10) + Piper catalog (D-01) + import (D-13)
          # + badges (D-11) + download/resume/cancel + uninstall (VOICE-07)
```
The existing sections (`st.subheader("TTS Engine")` 97-192, "Processing" 194, "LLM" 246, "News" 334) move *into* their tabs largely unchanged. **`st.tabs` renders every body each run** (not lazy) — keep the cached `_cached_voices` (lines 24-27, `@st.cache_data`) so tab-switching stays cheap.

**Cross-engine browser (D-10)** reuses the entire picker pattern already in this file (lines 112-163): `filter_voices` + `order_by_quality` + name search + `resolve_selected_voice_id`. Aggregate across engines via the new `registry` helper, add an engine filter column. The filter/order/search helpers are imported at lines 9-18.

**Custom-label editor (D-14)** writes via the new `voice_labels.set_label_overrides`; durable-pref read/write mirrors lines 168-172 (`get_setting`/`set_setting`, write-only-on-change).

**Background download + progress (ENGINE-04, D-08)** — copy RESEARCH Pattern 3 verbatim (`04-RESEARCH.md:296-331`): `st.session_state.dl_state` keyed by voice id, a daemon `threading.Thread`, and `@st.fragment(run_every="0.5s")` that reads shared state. **Never call `st.*` from the thread** (Anti-Patterns). Guard re-trigger across reruns via `dl_state` (Pitfall 3).

**Manual import (D-13)** — `st.file_uploader(accept_multiple_files=True)` for the `.onnx`+`.onnx.json` pair. The path-traversal guard is the existing `1_Upload.py:268-284` block (see Shared Patterns) — reuse verbatim. The save-button validation idiom (warn-list + `st.warning`/`st.success`) is at `5_Settings.py:346-388`.

**Uninstall (VOICE-07, D-16/D-17/D-18)** — confirm-before-delete + in-use block. The in-use check reads `jobs.tts_voice` and the `tts.default_voice.<engine>` keys; the delete mirrors `database.py:delete_job`'s `unlink(missing_ok=True)` (line 259). Backstop = Phase-3 `resolve_default_voice` (already wired, lines 143-145).

---

### `diana/dashboard/pages/1_Upload.py` (UI, MODIFY — D-11 badges only)

**Analog:** itself. The only change is adding install-state/footprint badges to the engine `selectbox` (lines 102-107). Badge text comes from the new `install_state` probe + manifest footprint ("Ready" / "~2.4 GB, downloads on first use"). Streamlit `selectbox` can't render rich per-option badges, so the badge likely renders as an `st.caption`/`st.info` below the engine select (mirroring the existing `_NATIVE_HINT` dismissible-info block at lines 184-195). **Do not** touch the voice picker logic (lines 109-176) — it already works and reuses the Phase-3 helpers.

---

## Shared Patterns

### Pure-helper module shape (Streamlit-free, unit-testable)
**Source:** `diana/tts/native_voices_macos.py` (whole file) + `diana/tts/native_os_engine.py:50-162`
**Apply to:** `downloads/downloader.py`, `tts/catalog.py`, `tts/voice_labels.py`, `tts/install_state.py`
Module-level functions (no class unless stateful), top-of-file prose docstring explaining the non-obvious logic, `logger = logging.getLogger(__name__)`, leading-underscore private helpers/constants, heavy/optional deps imported lazily inside functions. The pure transform is one function; the I/O is a thin wrapper around it — so the transform tests against a fixture with no I/O.

### Durable UI-only prefs via `app_settings`
**Source:** `diana/database.py:148-167` (`get_setting`/`set_setting`) + the db-wrapper-over-pure-helper at `diana/tts/registry.py:76-100`
**Apply to:** `voice_labels.py` (custom labels/tags D-14), dismiss flags, optional download state
```python
def get_setting(db_path, key, default=None): ...   # SELECT value FROM app_settings WHERE key=?
def set_setting(db_path, key, value): ...          # INSERT ... ON CONFLICT(key) DO UPDATE
```
Namespaced JSON-valued keys (`voice.labels.<engine>.<id>`). Write only on change (mirror `1_Upload.py:173-176`). Never use the load-once `config.py` singleton for these — `app_settings` survives restart without file editing (Phase-1 pattern; the non-technical-user constraint).

### Phase-3 voice filter / order / search (reuse verbatim — D-03)
**Source:** `diana/tts/native_os_engine.py:55-162` (`_fold`, `filter_voices`, `_matches_language`, `order_by_quality`, `resolve_default_voice`, `resolve_selected_voice_id`)
**Apply to:** `catalog.py` curation, the cross-engine browser, every catalog filter/search
Already imported and wired in both pages (`1_Upload.py:14-18`, `5_Settings.py:9-13`). Name search is accent-insensitive `_fold` + substring `in` — **never compile user-supplied regex** (ReDoS; Anti-Patterns). Filters point at catalog data instead of OS voices; language options derive from the manifest (D-03).

### Path-traversal guard for imports (HARD-03 / VOICE-04)
**Source:** `diana/dashboard/pages/1_Upload.py:268-284` (`os.path.basename` + resolved-prefix check)
**Apply to:** Manual import in the Voices tab (`file_uploader` + path entry)
```python
safe_name = os.path.basename(uploaded_file.name)        # strip path components
...
if not str(tmp_path.resolve()).startswith(str(tmp_dir.resolve())):
    st.error("Invalid filename."); st.stop()
```
Extend with the `.onnx`/`.onnx.json` extension allow-list (RESEARCH Pattern 5, `04-RESEARCH.md:366-374`). The destination dir is `paths.model_dir()`/`voices_dir()` (`paths.py:41-46`).

### Cheap, no-heavy-import detection (ENGINE-01)
**Source:** `diana/tts/registry.py:118-126` (`engine_is_ascii_only` static map) + `paths.py` filesystem probes
**Apply to:** `install_state.py` (all install/footprint badges)
Filesystem probe of `model_dir()`, never an engine SDK import. Mirrors the existing "resolve capability without pulling onnxruntime/piper" lane.

### File-cleanup idiom (uninstall + partial cleanup, VOICE-07)
**Source:** `diana/database.py:248-271` (`delete_job` — `Path(...).unlink(missing_ok=True)`, `shutil.rmtree(..., ignore_errors=True)`)
**Apply to:** `downloader.py` partial cleanup, Voices-tab uninstall
`unlink(missing_ok=True)` for files; glob `*.part` in `model_dir()` for the D-18 bulk clean. Confirm-before-delete + in-use block live in the UI (D-16/D-17).

---

## Test Patterns (Wave-0 scaffolds)

All seven test files follow the **Wave-0 guarded-import + `skipif` scaffold** so collection stays GREEN before implementation, then flips to live gates with zero edits. The canonical templates are `tests/test_native_os_engine.py` and `tests/test_native_voices_macos.py`.

**Guarded-import probe** (`test_native_os_engine.py:28-66`, `test_native_voices_macos.py:22-47`) — probe the likely module homes so the scaffold binds wherever the symbol lands:
```python
try:
    from diana.downloads.downloader import download_file  # noqa: F401
    _DL_AVAILABLE = True
except ImportError:
    download_file = None
    _DL_AVAILABLE = False

@pytest.mark.skipif(not _DL_AVAILABLE, reason="downloader implemented in Plan NN")
def test_...(tmp_path): ...   # real assertion body, never `pass`
```

**Fixture-driven pure-parse test** (`test_native_voices_macos.py:49-60`, `test_catalog.py` analog) — a small `voices.json` excerpt (2-3 entries incl. one multi-speaker) under `tests/fixtures/` (mirrors `tests/fixtures/say_voices.txt`); feed text to the pure `parse_manifest` seam.

**Mock-the-SDK / mock-the-DB** (`test_piper_engine.py:27-61` `patch.dict("sys.modules", {...})`; `test_native_os_engine.py:250` `patch("diana.database.get_setting", return_value=...)`) — for `test_voice_labels.py` (mock `get_setting`) and any downloader test that must avoid real `requests`.

**tmp_path fixtures** (`test_piper_engine.py:13-18`) — `test_downloader.py`/`test_install_state.py`/`test_uninstall.py` write fake `.onnx`/`.part` files into `tmp_path` and monkeypatch `paths.model_dir`/`shutil.disk_usage`.

**Real-resource skip-gated smoke** (`test_native_os_engine.py:131-151` skips when the resource is unavailable) — `test_downloader_net.py` uses `@pytest.mark.network` (register the marker in `pyproject.toml`, `04-RESEARCH.md:677`) and is excluded by default.

**Registry cheap-probe assertions** (`test_tts_registry.py:19-49`) — model for `test_install_state.py` true/false probe assertions.

**Run command (user memory — always `.venv`):**
`.venv/bin/python -m pytest tests/test_downloader.py tests/test_catalog.py tests/test_install_state.py tests/test_voice_import.py tests/test_voice_labels.py tests/test_uninstall.py -x`

---

## No Analog Found

| File | Role | Data Flow | Reason / Guidance |
|------|------|-----------|-------------------|
| `diana/data/samples/*.mp3` | binary data asset | static | No bundled binary media exists in-repo today. Closest *structural* analog is `tests/fixtures/say_voices.txt` (a bundled snapshot the code reads at runtime). Guidance: place under `diana/data/`, and flag for the Phase-6 packager to add to `pyproject.toml` package-data / `MANIFEST.in` (per `04-RESEARCH.md:571,574`). `pyproject.toml` currently has **no** `[tool.setuptools.package-data]` (verified) — the planner must add one. |
| Background download thread + `st.fragment` polling | concurrency pattern | event-driven | No existing thread-spawning UI in the codebase (the `JobWorker` thread in `worker.py` is the only thread, and ENGINE-04 forbids reusing it). Use RESEARCH Pattern 3 (`04-RESEARCH.md:296-331`, Streamlit-official polling) as the authoritative pattern — it has no in-repo precedent to copy. |

---

## Metadata

**Analog search scope:** `diana/tts/` (registry, base, piper_engine, kokoro_engine, native_os_engine, native_voices_macos), `diana/dashboard/pages/` (1_Upload, 5_Settings), `diana/database.py`, `diana/paths.py`, `diana/config.py`, `tests/` (test_native_os_engine, test_native_voices_macos, test_piper_engine, test_tts_registry, fixtures layout), `pyproject.toml`.
**Files scanned:** 14 source files read in full + targeted greps on config/pyproject.
**Pattern extraction date:** 2026-06-15
