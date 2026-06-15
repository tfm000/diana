# Phase 4: Engine Management & Voice Catalog - Research

**Researched:** 2026-06-15
**Domain:** On-demand model/voice download + cache layer, Streamlit voice-management UI, Piper voice catalog (HuggingFace `rhasspy/piper-voices`), Kokoro model download
**Confidence:** HIGH (all external facts verified live via curl/python against real endpoints this session)

## Summary

Phase 4 builds an **engine-agnostic, on-demand download/cache layer** and a **voice-management UI** (a new "Voices" tab in a restructured Settings page) on top of Diana's existing Protocol-based TTS architecture. The download layer is proven end-to-end this phase by the **Piper per-voice catalog** (VOICE-01..04) and the **Kokoro single-model download** (D-19), with heavy engines deferred to Phase 5. Everything is built with **stdlib + `requests` (already a dependency)** — no new download library is needed or justified.

All the load-bearing external unknowns were verified live this session: the `rhasspy/piper-voices` `voices.json` manifest schema (`key`/`name`/`language{}`/`quality`/`num_speakers`/`speaker_id_map`/`files{path: {size_bytes, md5_digest}}`/`aliases`), the raw-download URL pattern (`https://huggingface.co/rhasspy/piper-voices/resolve/main/<path>`), per-voice sample audio (`<voice-dir>/samples/speaker_0.mp3`, ~84 KB), HuggingFace **and** GitHub-release CDN **HTTP Range support** (both return `206 Partial Content` — resumable downloads work), `shutil.disk_usage()` cross-platform free-byte reporting, the Streamlit-official **polling pattern** for background work (never call `st.*` from a spawned thread), and the **`PiperVoice.load()` sibling-config convention** (`{model}.onnx` auto-loads `{model}.onnx.json`).

**Primary recommendation:** Add a generic `diana/downloads/` module (stdlib + `requests`) implementing a resumable streaming downloader (Range → `.part` → md5-verify → atomic `os.replace`) plus a `diana/tts/catalog.py` for the bundled+refreshable Piper manifest. Drive downloads from the UI via the **Streamlit polling pattern** (`st.fragment(run_every=...)` reading a thread-shared progress dict), never from the worker. Land Piper voices and the Kokoro model in `paths.model_dir()`. Reuse the Phase-3 `filter_voices`/`order_by_quality` helpers verbatim for the catalog. Store custom labels/tags and download/dismiss state in the existing `app_settings` key/value table as JSON-valued keys. Make every pure unit (manifest parse, filter/order, resolve, disk-check, resume-offset math, label-merge, install-state probe, import-filename validation) testable on macOS; flag real-network download, Streamlit progress UX, and `file_uploader` as manual/integration verification.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Catalog scope & layout (VOICE-01):**
- **D-01:** Hybrid curation. Piper catalog shows a curated best-per-language subset by default, with a "Show all voices" toggle expanding to the full `rhasspy/piper-voices` manifest (~900+ voices). Manual import (D-13) covers anything not listed.
- **D-02:** Bundled manifest snapshot + manual refresh. Ship a curated voices-manifest JSON inside the app so the catalog browses instantly and offline; a manual "Refresh catalog" action re-fetches the live manifest. Actual voice files always download on demand regardless.
- **D-03:** Hybrid layout, reusing Phase 3 controls. Reuse Phase 3 language/quality filters + name-search **widgets** everywhere (pointed at catalog data, with language options derived from the manifest, not OS voices). Render a **flat list** in the curated default view; **group by language (collapsible sections)** in the "Show all" view. One filter pattern; grouping only where it earns its keep.

**Download experience (ENGINE-02, ENGINE-03, ENGINE-04):**
- **D-04:** Threshold-based confirmation. Small files (Piper voices, ~20–60 MB) install one-click; downloads above a size threshold (e.g. >200 MB — the GB-scale engine models reused in Phase 5) show an explicit confirm with the footprint before starting.
- **D-05:** **Universal disk-space pre-check that gates EVERY download** (including one-click small ones). Before any download starts, check free space; if insufficient, show an error badge and **refuse to start** — block, and show **needed vs. free**. Never begin a download that can't complete.
- **D-06:** Manual Resume for interrupted downloads. Keep the partial (`.part`) file on crash/quit/network drop; surface an explicit "Resume" control on incomplete downloads (resumes from the partial, not a restart).
- **D-07:** Cancel allowed, partial kept. A Cancel/Stop control halts an in-progress download and **retains the `.part`** so it can be resumed later (D-06).
- **D-08:** Byte progress + UI-triggered, cache-landed. Downloads show visible byte progress; triggered **only from the UI** (never inside the worker/job — ENGINE-04) and land in the per-user cache (`paths.model_dir()` / `voices_dir()`).

**Where the UI lives (ENGINE-03, VOICE-06):**
- **D-09:** Settings restructured into tabs, with a dedicated "Voices" tab as the management hub (catalog + downloads + cross-engine browser + install state + install/uninstall). `5_Settings.py` grows `st.tabs` (e.g. General / Voices / …) rather than adding a new top-level page.
- **D-10:** Unified cross-engine browser, filtered by engine (VOICE-06). One list of every engine's voices together (native_os, Kokoro, Piper), with an engine filter/column plus the Phase 3 language/quality filters + search. native_os voices appear here too, as browse/preview/label-only — nothing to download/uninstall.
- **D-11:** Install-state + footprint badges on the Voices tab AND the Upload engine dropdown (ENGINE-03) — e.g. "Ready" / "~2.4 GB, downloads on first use". Detection must be **cheap, with no heavy imports** (ENGINE-01).

**Preview, import & custom labels (VOICE-03, VOICE-04, VOICE-06):**
- **D-12:** Preview = bundle curated samples + fetch the rest, with caching. Pre-recorded samples for the curated default set ship in-app (offline preview); "Show all"/other catalog voices fetch the sample clip on demand (rhasspy ships one per voice, ~100 KB) and cache it in the per-user dir. Installed voices preview via live synthesis (Phase 3 path).
- **D-13:** Manual import via BOTH in-app upload and path entry (VOICE-04). A `file_uploader` accepts the `.onnx` + `.onnx.json` pair (validate the pair, read metadata from the JSON, copy into the per-user voices dir) — the true no-terminal path — AND a "point to a path on disk" option.
- **D-14:** Editable labels = override attributes + custom tags (VOICE-06). User can override prelabeled language/quality tier/gender/display name AND add free-text custom tags; overrides + tags persist per voice id (UI-only, survive restart) and feed the same filters/search. Built on Phase 3's `TTSVoice` attribute layer. Storage shape = planner's choice (candidate: `app_settings` or a small dedicated table).
- **D-15:** Custom labels apply across all engines — editing/tagging works for any voice in the cross-engine browser (native_os, Kokoro, Piper), not just downloadable ones.

**Uninstall / manage (= VOICE-07):**
- **D-16:** Uninstall a fully-installed voice requires confirmation, showing the freed space before deletion.
- **D-17:** Block uninstall of an in-use voice. If the voice is a current per-job choice or a per-engine default, refuse and tell the user to switch first. (Phase 3's `resolve_default_voice` still guards against a stale id at selection time as a backstop.)
- **D-18:** Partial-file cleanup: per-item + bulk. Each catalog row with a partial shows a "Remove partial" action, plus a single "Clean up partial downloads" button that clears all orphaned `.part` files at once. (native_os has nothing to uninstall.)

**Engine scope (success-criterion boundary):**
- **D-19:** Engine-agnostic management UX + generic download/cache layer, proven via Piper + Kokoro this phase. The browser/preview/labels/badges/install/uninstall UX and the download/cache/disk-check/resume/cancel machinery are generic across all present engines. This phase wires the layer to Piper (per-voice catalog) and Kokoro (single-model download — replaces today's wget-hint error with an in-UI download). Heavy engines (Orpheus / F5-TTS / Fish) are NOT built here — Phase 5. native_os has nothing to download/uninstall.

### Claude's Discretion
- Exact download mechanism (streaming HTTP with Range/`content-length` for resumability, off the UI thread), threading model, and the size threshold value for D-04.
- Storage shape for custom labels/tags + dismissed flags (candidate: Phase-1 `app_settings`); manifest JSON schema and bundled snapshot location; sample-cache directory layout.
- Concurrent-download policy (serialize vs. parallel) and the `.part` file naming/locking convention.
- Whether install-state detection (ENGINE-01) is a filesystem probe of the cache vs. an engine-reported capability call — must stay cheap (no heavy SDK imports).
- Exact tab names/order in the restructured Settings page; how Kokoro's "single model, many baked-in voices" maps onto the per-voice catalog UI (likely an engine-level "model installed?" badge rather than per-voice rows).

### Deferred Ideas (OUT OF SCOPE)
- Heavy-engine (Orpheus / F5-TTS / Fish) download + catalogs → Phase 5, reusing this phase's generic layer.
- Standalone dedicated voice-browser page (VNEXT-01) → future; this phase puts the browser in the Settings Voices tab.
- Volume/pitch controls → not requested; out of scope. Per-job speed already exists.
- `phase7-setup-scripts-per-user-paths.md` (installer/bootstrap model downloads) → Phase 6/7.
- `phase7-settings-env-var-key-exfiltration.md` (HARD-03) → Phase 7 security.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ENGINE-01 | Engine availability/capability detected cheaply, no heavy imports | Install-state = filesystem probe of `model_dir()`/`voices_dir()` for `{id}.onnx` (Piper) / `kokoro-v1.0*.onnx` (Kokoro). Confirmed: no need to import onnxruntime/piper. See "Cheap install-state detection". |
| ENGINE-02 | On-demand download: byte progress, resumability, disk-space pre-check | Verified live: HF + GitHub CDN return `206 Partial Content` to `Range` requests; resumable `.part` + md5 + atomic `os.replace` works end-to-end; `shutil.disk_usage().free` cross-platform. See "Resumable download" + "Disk-space pre-check". |
| ENGINE-03 | Picker shows install-state + footprint badges | Footprint from manifest `size_bytes` (sum the `.onnx`+`.onnx.json`); install-state from filesystem probe. Badges render in the Voices tab + `1_Upload.py` engine dropdown. |
| ENGINE-04 | Downloads land in per-user cache, UI-triggered only, never in worker | `paths.model_dir()` is the Piper + Kokoro cache home. Download started by a button on the Voices tab, run on a UI-spawned thread polled via `st.fragment(run_every=...)`. The `JobWorker` (`worker.py`) is never touched. |
| VOICE-01 | Browse Piper catalog from the manifest | Bundled curated `voices.json` snapshot + "Refresh catalog" fetch of live manifest. Schema fully documented below. |
| VOICE-02 | Download/install catalog voices, no terminal | Download `.onnx` + `.onnx.json` pair into `model_dir()`; `PiperVoice.load` auto-finds the sibling `.onnx.json`. |
| VOICE-03 | Preview (pre-recorded sample if not installed; live if installed) | Bundle curated `speaker_0.mp3` samples; fetch+cache the rest from `<voice-dir>/samples/speaker_0.mp3`; live synth via existing `create_engine`→`synthesize`→`st.audio` path. |
| VOICE-04 | Manual import of Piper `.onnx` + `.onnx.json` via UI | `st.file_uploader(accept_multiple_files=True)` for the pair + path-entry option; validate filenames (zip-slip/traversal), read metadata from `.onnx.json`, copy into `voices_dir()`/`model_dir()`. |
| VOICE-05 | Select voice per job | Already shipped (Phase 3 Upload picker). New voices appear automatically once on disk. |
| VOICE-06 | Edit/add custom labels, persisted UI-only, cross-engine browse/select | Override `TTSVoice` attributes + custom tags stored in `app_settings` as JSON; cross-engine browser aggregates `get_engine_voices()` over `list_engines()`. |
| VOICE-07 | Uninstall installed voice (confirmed, freed space shown, blocked if in-use) + clean partials (per-item + bulk) | Delete `{id}.onnx`(+`.onnx.json`) from `model_dir()`; block when id == any job's `tts_voice` or a per-engine default key; glob `*.part` for cleanup. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Manifest parse / curation / filter / order | Pure helpers (`diana/tts/catalog.py` + reused `native_os_engine` helpers) | — | No I/O, no Streamlit — unit-testable on macOS; reuses Phase-3 `filter_voices`/`order_by_quality`. |
| Resumable download / md5 / atomic rename | Generic download module (`diana/downloads/`) | — | Engine-agnostic; reused by Piper + Kokoro now, heavy engines Phase 5 (D-19). stdlib + `requests` only. |
| Disk-space pre-check | Generic download module | — | `shutil.disk_usage()`; gates every download (D-05). |
| Install-state / footprint detection | Registry/catalog (cheap filesystem probe) | — | ENGINE-01: no heavy SDK import; probes `model_dir()`. |
| Custom labels / tags / dismiss / download state | Persistence (`app_settings` via `database.py`) | — | Durable UI-only prefs (Phase-1 pattern); never the load-once config singleton. |
| Background download orchestration + live progress | Streamlit UI (`5_Settings.py` Voices tab) | Thread + shared dict | Official Streamlit polling pattern; UI-triggered only (ENGINE-04). |
| Cross-engine voice browser / preview / import / uninstall UI | Streamlit UI (`5_Settings.py` Voices tab) | Registry + download module | D-09/D-10 management hub. |
| Voice file resolution at synth time | TTS engine (`piper_engine._resolve_model_path`) | — | Already resolves `{voice}.onnx` in `model_dir`; downloaded/imported files become selectable with zero engine edits. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `requests` | 2.33.1 (installed; `>=2.31.0` pinned) | Streaming HTTP download with `Range` header + `iter_content` | Already a Diana dependency; stdlib-quality streaming + redirect handling; no new dep. [VERIFIED: installed in .venv; end-to-end resumable download tested live this session] |
| `streamlit` | 1.56.0 (installed; `>=1.30.0` pinned) | UI: `st.tabs`, `st.file_uploader`, `st.progress`, `st.status`, `st.fragment` | Already the dashboard framework; 1.56 has `st.fragment(run_every=...)` for polling. [VERIFIED: `st.fragment`/`st.status`/`st.progress` all present in installed build] |
| `hashlib` (stdlib) | — | md5 verification of downloaded files against manifest `md5_digest` | Manifest ships md5 per file; stdlib. [VERIFIED: md5 of real HF file matched manifest this session] |
| `shutil` (stdlib) | — | `disk_usage(path)` free-byte pre-check (D-05) | Cross-platform (macOS + Windows); returns `(total, used, free)`. [VERIFIED: returns named tuple on macOS this session] |
| `os` (stdlib) | — | `os.replace()` atomic same-filesystem rename of `.part` → final | Atomic on POSIX + Windows when src/dst share a filesystem. [VERIFIED: `os.replace` succeeded this session] |
| `json` (stdlib) | — | Parse `voices.json` manifest; serialize custom labels into `app_settings` | Manifest is JSON; `app_settings.value` is TEXT — store JSON strings. |
| `piper-tts` | 1.4.2 (installed; `>=1.0.0` pinned) | Live preview/synthesis of installed voices (existing path) | Already wired in `piper_engine.py`; `PiperVoice.load` auto-finds sibling `.onnx.json`. [VERIFIED: installed; load convention confirmed via official sources] |
| `kokoro-onnx` | 0.5.0 (installed; `>=0.4.0` pinned) | Synthesis once the Kokoro model is downloaded (existing path) | Already wired in `kokoro_engine.py`. [VERIFIED: installed] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `threading` (stdlib) | — | Run a download off the Streamlit script thread | When a download must not block the UI; thread writes to a shared dict, UI polls (never call `st.*` from the thread). |
| `pathlib` (stdlib) | — | Path building, `.part` naming, glob `*.part` | Throughout; matches Diana's existing `paths.py` style. |
| `tempfile` (stdlib) | — | Stage `file_uploader` bytes before validation/copy | Import flow (VOICE-04). |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `requests` streaming | `huggingface_hub` (`hf_hub_download`) | `huggingface_hub` gives resumable downloads + caching for free, BUT it is a NEW heavy dependency (pulls `tqdm`, `filelock`, `fsspec`, `huggingface-hub`), uses its own cache layout (not Diana's `model_dir()`), and couples the generic layer to HF specifically — Kokoro's GitHub-release assets wouldn't go through it. The CONTEXT explicitly prefers stdlib `requests`. **Rejected.** |
| `requests` streaming | `urllib.request` (stdlib only) | Zero deps, but manual redirect/Range/stream handling is clumsier and `requests` is already present. **Rejected** — no benefit. |
| Background thread + polling | `st.write_stream` / generator with periodic `st.rerun()` | A generator loop blocks the script run for the whole download (UI frozen, no cancel). The thread+`st.fragment` polling pattern is the Streamlit-official approach and supports Cancel. **Rejected** the generator approach. |
| `os.replace` atomic rename | write directly to final path | A crash mid-write leaves a corrupt "complete-looking" file. The `.part` + verify + atomic-rename pattern is the whole point of D-06. **Keep `.part`.** |
| New dedicated DB table | `app_settings` JSON values | A dedicated `voice_labels` table is cleaner long-term but adds a migration + access functions; `app_settings` is the established Phase-1 durable-prefs pattern and is sufficient. **Recommend `app_settings`** (see "Storage shape"). |

**Installation:** No new packages required. All four touched libraries (`requests`, `streamlit`, `piper-tts`, `kokoro-onnx`) are already pinned in `requirements.txt` and installed in `.venv`.

```bash
# Nothing to install — verify only:
.venv/bin/python -c "import requests, streamlit, piper, kokoro_onnx; print('all present')"
```

## Package Legitimacy Audit

> All packages this phase uses are pre-existing Diana dependencies. No new package is added. slopcheck ran clean.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `requests` | PyPI | mature (10+ yrs) | ~hundreds of M/wk | github.com/psf/requests | [OK] | Approved (existing dep) |
| `streamlit` | PyPI | mature | ~millions/wk | github.com/streamlit/streamlit | [OK] | Approved (existing dep) |
| `piper-tts` | PyPI | established | — | github.com/OHF-Voice/piper1-gpl | [OK] | Approved (existing dep) |
| `kokoro-onnx` | PyPI | established | — | github.com/thewh1teagle/kokoro-onnx | [OK] | Approved (existing dep) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*Verified via `slopcheck install requests streamlit piper-tts kokoro-onnx` this session — all 4 returned `[OK]` on PyPI. All four already pinned in `requirements.txt` and installed in `.venv` (versions confirmed: requests 2.33.1, streamlit 1.56.0, piper-tts 1.4.2, kokoro-onnx 0.5.0).*

## Architecture Patterns

### System Architecture Diagram

```text
                         ┌─────────────────────────────────────────┐
                         │  5_Settings.py — st.tabs (D-09)          │
                         │  [ General ] [ Voices ] [ … ]            │
                         └───────────────┬─────────────────────────┘
                                         │ Voices tab
        ┌────────────────────────────────┼───────────────────────────────────┐
        │                                │                                    │
        ▼                                ▼                                    ▼
┌────────────────┐          ┌──────────────────────┐            ┌────────────────────────┐
│ Cross-engine    │          │ Piper catalog (D-01)  │            │ Manual import (D-13)    │
│ browser (D-10)  │          │ curated | Show all    │            │ file_uploader + path    │
│ aggregate       │          │ filter/search (D-03)  │            │ validate pair → copy    │
│ get_engine_     │          └──────────┬────────────┘            └───────────┬────────────┘
│ voices() over   │                     │ Install / Resume / Cancel           │
│ list_engines()  │                     ▼                                     │
│ + labels (D-14) │          ┌────────────────────────────┐                  │
└───────┬─────────┘          │ UI-spawned download thread  │                  │
        │                    │ (ENGINE-04 — NOT the worker)│                  │
        │ badges (D-11)      │  1. disk_usage() pre-check  │ (D-05)           │
        ▼                    │  2. GET Range → .part       │ (D-06)           ▼
┌────────────────┐          │  3. md5 verify vs manifest  │        ┌────────────────────┐
│ install-state  │◀─────────│  4. os.replace → final      │───────▶│ paths.model_dir()   │
│ probe (cheap,  │ reads     │  writes progress to shared  │ lands  │ paths.voices_dir()  │
│ ENGINE-01)     │ filesystem│  dict; UI polls via         │ files  │  {id}.onnx          │
└────────────────┘          │  st.fragment(run_every=…)   │        │  {id}.onnx.json     │
        │                    └────────────┬───────────────┘        │  kokoro-v1.0*.onnx  │
        │                                 │ Content-Range = truth   │  voices-v1.0.bin    │
        ▼                                 ▼                         │  *.part (resumable) │
┌────────────────┐          ┌────────────────────────────┐        └─────────┬──────────┘
│ 1_Upload.py     │          │ Remote sources              │                  │ resolved at synth
│ engine dropdown │          │ HF rhasspy/piper-voices     │                  ▼
│ + badges (D-11) │          │ (resolve/main/<path>, 206)  │        ┌────────────────────┐
└────────────────┘          │ GitHub kokoro-onnx release  │        │ piper_engine /      │
                            │ (assets, 206)               │        │ kokoro_engine       │
                            └────────────────────────────┘        │ live preview/synth  │
                                                                    └────────────────────┘

         Persistence: app_settings(key,value) ── custom labels/tags (D-14), dismiss flags,
                      optional per-download state.   Worker (worker.py) is UNTOUCHED (ENGINE-04).
```

### Recommended Project Structure
```
diana/
├── downloads/                  # NEW — generic, engine-agnostic (reused Phase 5)
│   ├── __init__.py
│   └── downloader.py           # resumable streaming download, disk-check, md5, atomic rename, cancel
├── tts/
│   ├── catalog.py              # NEW — Piper manifest parse/curate/footprint; bundled snapshot + refresh
│   ├── voice_labels.py         # NEW (or fold into registry) — custom label/tag merge over TTSVoice (D-14)
│   ├── install_state.py        # NEW (or fold into registry) — cheap filesystem probe (ENGINE-01)
│   ├── registry.py             # MODIFY — wire install-state + cross-engine aggregation helpers
│   ├── piper_engine.py         # (no change needed — _resolve_model_path already finds {voice}.onnx)
│   └── kokoro_engine.py        # MODIFY (optional) — route model download via downloads/ (D-19)
├── data/
│   └── piper_voices_curated.json   # NEW bundled curated manifest snapshot (D-02) — package data
│   └── samples/                    # NEW bundled curated preview clips (D-12)
├── dashboard/pages/
│   ├── 5_Settings.py           # MODIFY — restructure into st.tabs; add Voices tab (D-09)
│   └── 1_Upload.py             # MODIFY — add install-state/footprint badges to engine dropdown (D-11)
└── database.py                 # (reuse get_setting/set_setting; no schema change required)
```
*Module homes for `voice_labels`/`install_state` are planner's choice — they may be functions inside `registry.py` or `catalog.py`. The key constraint: the download module stays engine-agnostic (no `piper`/`kokoro` import), and the cheap-probe + label-merge logic stays Streamlit-free and unit-testable.*

### Pattern 1: Resumable streaming download (`.part` → md5 → atomic rename)
**What:** Stream a file with `requests`, support resume via HTTP `Range`, verify md5 against the manifest, then atomically rename `.part` → final.
**When to use:** Every Piper voice file and the Kokoro model/voices files.
**VERIFIED live this session** against the real HuggingFace file (`en_US-lessac-medium.onnx.json`, 4885 bytes, md5 `c1f2b7bddefe113f3255ff9ef234cfd3`) — interruption at 1000 bytes, resume via `Range: bytes=1000-` returned `206`, final size + md5 matched, `os.replace` succeeded.

```python
# Source: pattern verified live against huggingface.co + github releases (this session)
import hashlib, os
from pathlib import Path
import requests

def download_file(url: str, dest: Path, expected_md5: str | None = None,
                  expected_size: int | None = None,
                  progress=None, cancel=None) -> None:
    """Resumable streaming download. progress(downloaded, total); cancel() -> bool."""
    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    offset = part.stat().st_size if part.exists() else 0

    headers = {"Range": f"bytes={offset}-"} if offset else {}
    with requests.get(url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        # PITFALL: HF's first GET / a HEAD-through-redirect can report Content-Length: 0.
        # The reliable total comes from the manifest size_bytes, or from the
        # Content-Range header on a 206 ("bytes 1000-4884/4885" -> 4885).
        total = expected_size
        cr = r.headers.get("Content-Range")
        if total is None and cr and "/" in cr:
            total = int(cr.rsplit("/", 1)[-1])
        if total is None:
            total = int(r.headers.get("Content-Length", 0)) + offset

        mode = "ab" if offset and r.status_code == 206 else "wb"
        if mode == "wb":
            offset = 0  # server ignored Range; restart cleanly
        with open(part, mode) as f:
            downloaded = offset
            for block in r.iter_content(chunk_size=1 << 16):  # 64 KB
                if cancel and cancel():
                    return  # D-07: leave .part in place for Resume (D-06)
                f.write(block)
                downloaded += len(block)
                if progress:
                    progress(downloaded, total)

    if expected_md5:
        actual = hashlib.md5(part.read_bytes()).hexdigest()
        if actual != expected_md5:
            part.unlink(missing_ok=True)  # corrupt — drop it, do not rename
            raise ValueError(f"md5 mismatch for {dest.name}: {actual} != {expected_md5}")
    os.replace(part, dest)  # atomic on same filesystem (POSIX + Windows)
```

### Pattern 2: Universal disk-space pre-check (D-05)
**What:** Before any download, refuse if free space < needed (+ a safety margin). The target subdir may not exist yet, so walk up to the first existing ancestor.
**VERIFIED live this session** on macOS — `shutil.disk_usage()` returns `(total, used, free)`; ancestor-walk resolves a not-yet-created target.

```python
# Source: verified live on macOS (this session); shutil.disk_usage is cross-platform
import shutil
from pathlib import Path

def has_space(target: Path, needed_bytes: int, margin: float = 1.10) -> tuple[bool, int]:
    """Return (ok, free_bytes). margin reserves headroom over the raw need."""
    p = target
    while not p.exists():           # disk_usage needs an existing path
        p = p.parent
    free = shutil.disk_usage(p).free
    return free >= int(needed_bytes * margin), free
```

### Pattern 3: Background download + Streamlit polling (ENGINE-04, D-08)
**What:** Spawn a worker thread that writes progress to a shared dict; the UI reads it via `st.fragment(run_every=...)`. **Do NOT call `st.*` from the thread** — the Streamlit-official rule.
**When to use:** The Voices-tab Install/Resume action.
**CITED:** docs.streamlit.io/develop/concepts/design/multithreading — "do not call Streamlit commands from custom threads"; use containers initialized before the thread and read shared state from the main script.

```python
# Source: docs.streamlit.io/develop/concepts/design/multithreading (polling pattern)
import threading
import streamlit as st

# Shared, thread-safe-enough state (single writer thread, single reader script).
# Keyed by voice id so concurrent UI reruns don't collide.
if "dl_state" not in st.session_state:
    st.session_state.dl_state = {}   # {voice_id: {"downloaded":..,"total":..,"done":..,"error":..}}

def start_download(voice_id, url, dest, md5, size):
    state = {"downloaded": 0, "total": size, "done": False, "error": None, "cancel": False}
    st.session_state.dl_state[voice_id] = state
    def _run():
        try:
            download_file(url, dest, md5, size,
                          progress=lambda d, t: state.update(downloaded=d, total=t),
                          cancel=lambda: state["cancel"])
            state["done"] = True
        except Exception as e:        # noqa: BLE001 — surface to UI, never st.* here
            state["error"] = str(e)
    threading.Thread(target=_run, daemon=True).start()

@st.fragment(run_every="0.5s")        # polls without a full-page rerun
def render_progress(voice_id):
    state = st.session_state.dl_state.get(voice_id)
    if not state:
        return
    if state["error"]:
        st.error(f"Download failed: {state['error']}")  # called from SCRIPT thread, OK
    elif state["done"]:
        st.success("Installed.")
    else:
        total = state["total"] or 1
        st.progress(min(state["downloaded"] / total, 1.0),
                    text=f"{state['downloaded']/1e6:.1f} / {total/1e6:.1f} MB")
```

### Pattern 4: Cheap install-state detection (ENGINE-01, D-11)
**What:** Detect whether a voice/model is installed by **probing the filesystem cache** — never by importing the engine SDK.
**Why:** ENGINE-01 forbids heavy imports; this mirrors Diana's existing `engine_is_ascii_only()` "no engine import" lane.

```python
# Piper voice installed iff its .onnx exists in model_dir (matches _resolve_model_path)
from diana import paths

def piper_voice_installed(voice_id: str) -> bool:
    return (paths.model_dir() / f"{voice_id}.onnx").exists()

def piper_footprint_bytes(voice_id: str) -> int:
    f = paths.model_dir() / f"{voice_id}.onnx"
    return f.stat().st_size if f.exists() else 0  # else read from manifest size_bytes

# Kokoro = engine-level "model installed?" (single model, many baked-in voices — D-19)
def kokoro_model_installed() -> bool:
    md = paths.model_dir()
    onnx = any((md / n).exists() for n in
               ("kokoro-v1.0.onnx", "kokoro-v1.0.fp16.onnx", "kokoro-v1.0.int8.onnx"))
    return onnx and (md / "voices-v1.0.bin").exists()
```

### Pattern 5: Import-filename validation (HARD-03 traversal/zip-slip defense, VOICE-04)
**What:** When importing via `file_uploader` or a path, validate the basename and confirm the resolved destination stays inside `model_dir()`/`voices_dir()`. Reuses the exact guard already in `1_Upload.py:268-284`.
**Why:** A crafted `uploaded_file.name` like `../../etc/evil.onnx` or an absolute path must not escape the cache dir.

```python
# Source: mirrors the existing guard in diana/dashboard/pages/1_Upload.py:268-284
import os
from pathlib import Path
from diana import paths

def safe_voice_dest(uploaded_name: str) -> Path:
    base = os.path.basename(uploaded_name)            # strip any path components
    if not (base.endswith(".onnx") or base.endswith(".onnx.json")):
        raise ValueError("Only .onnx and .onnx.json files are accepted.")
    dest_dir = paths.model_dir()
    dest = dest_dir / base
    if not str(dest.resolve()).startswith(str(dest_dir.resolve())):
        raise ValueError("Invalid filename.")          # traversal blocked
    return dest
```

### Anti-Patterns to Avoid
- **Calling `st.progress`/`st.write` from the download thread.** Streamlit-official guidance forbids it (ScriptRunContext leak → "fatal errors or unexpected behavior"). Write to shared state; render from the script thread (Pattern 3).
- **Trusting a HEAD request (or first GET) for total size on HuggingFace.** The 307→CDN redirect chain reports `Content-Length: 0` on the first hop. Use the manifest `size_bytes` as the primary truth; `Content-Range` on the 206 as the runtime cross-check. (Verified live this session.)
- **Writing the download straight to the final filename.** A crash leaves a corrupt-but-complete-looking file that the install-state probe would treat as "Ready." Always `.part` → verify → `os.replace`.
- **Running downloads in `JobWorker`/`pipeline.py`.** ENGINE-04 forbids it; downloads are UI-triggered only. The worker stays document-conversion-only.
- **Re-triggering a download on every Streamlit rerun.** A naive `if st.button("Install"): download(...)` inside the script body re-fires whenever the button's state is truthy across reruns. Guard with session-state ("already started for this voice_id") and the thread-shared `dl_state` (Pattern 3).
- **Importing onnxruntime/piper just to show a badge.** Violates ENGINE-01. Filesystem probe only (Pattern 4).
- **Re-fetching the live manifest on page load.** D-02: browse from the bundled snapshot; the live fetch is the explicit "Refresh catalog" action only.
- **Unbounded regex on manifest/label free-text.** Custom tags (D-14) and the name search are user free-text; keep matching to plain substring/`in` (the Phase-3 `_fold` + `in` approach) — no user-supplied regex (ReDoS).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP streaming + redirects + Range | Custom socket/urllib download loop | `requests` (`stream=True`, `iter_content`, `Range` header) | Already a dep; handles redirects (HF 307→CDN), TLS, chunked transfer. |
| Atomic file replace | Write-then-`shutil.move` with manual checks | `os.replace()` | Atomic on the same filesystem on both POSIX and Windows; one call. |
| Free-space check | `os.statvfs` (POSIX-only) | `shutil.disk_usage()` | Cross-platform (Windows too); CONTEXT requires macOS + Windows. |
| md5 hashing | Custom chunked digest | `hashlib.md5(...)` | Stdlib; manifest ships `md5_digest` per file. |
| Background-task UI refresh | Manual `st.rerun()` loops / `time.sleep` in script | `st.fragment(run_every=...)` | Built-in periodic fragment refresh (Streamlit 1.56) — no full-page rerun, no frozen UI. |
| Piper config discovery | Parse/guess the config path | `PiperVoice.load(model)` auto-loads `{model}.onnx.json` | Library convention (verified) — just land both files side-by-side. |
| Voice filtering/ordering/search | New filter functions | Phase-3 `filter_voices` / `order_by_quality` / `_fold` (`native_os_engine.py`) | D-03 explicitly reuses these; accent-insensitive search already solved. |
| Durable UI prefs | New config file / new singleton | `app_settings` via `get_setting`/`set_setting` | Phase-1 established pattern; survives restart; sidesteps the load-once config singleton. |
| Stale-default guard | New validation | Phase-3 `resolve_default_voice` | Already validates a remembered id against the live list (D-17 backstop). |
| Path-traversal guard | New sanitizer | The existing `1_Upload.py:268-284` `os.path.basename` + resolved-prefix check | Proven in-repo pattern; reuse verbatim. |

**Key insight:** Nearly every primitive this phase needs is either stdlib (`shutil`, `hashlib`, `os`, `json`, `threading`, `tempfile`, `pathlib`) or an existing Diana dependency (`requests`, `streamlit`) or an existing Diana helper (`filter_voices`, `resolve_default_voice`, `get_setting`/`set_setting`, the upload-dir traversal guard, `piper_engine._resolve_model_path`). The genuinely new code is thin glue: a resumable downloader, a manifest parser/curator, an install-state probe, a label-merge layer, and the Voices-tab UI.

## Common Pitfalls

### Pitfall 1: HuggingFace total-size is not in HEAD / first GET
**What goes wrong:** Code calls `requests.head(url)` (or reads `Content-Length` from the first GET) to size the progress bar and disk-check, gets `0`, and the progress bar/disk-check is wrong.
**Why it happens:** `resolve/main/<path>` returns a `307` to `/api/resolve-cache/...` then a `302`/`200` on the CDN; intermediate hops carry their own (tiny/zero) `Content-Length`. (Verified live: first streaming GET reported `Content-Length: 0`.)
**How to avoid:** Use the **manifest `size_bytes`** as the authoritative total for the disk-check and the progress denominator. As a runtime cross-check, parse `Content-Range` (`bytes <start>-<end>/<total>`) from the `206` response. (Verified: `Content-Range: bytes 1000-4884/4885`.)
**Warning signs:** Progress bar jumps to 100% immediately, or disk-check passes/fails nonsensically.

### Pitfall 2: Server ignores the Range header → silent restart appended to `.part`
**What goes wrong:** If a proxy/CDN returns `200` (not `206`) to a `Range` request, opening the `.part` in append mode duplicates the already-downloaded prefix → corrupt file, md5 mismatch.
**Why it happens:** Not every endpoint honors `Range`; the response status distinguishes them (`206` honored, `200` ignored).
**How to avoid:** Check `r.status_code`: append (`ab`) only on `206`; on `200`, reset offset to 0 and open `wb`. (Pattern 1 does this.) HF + GitHub both honored `Range` with `206` this session, but defensive handling is cheap and protects against CDN changes.
**Warning signs:** md5 mismatch on a file that downloaded "successfully"; `.part` larger than the manifest size.

### Pitfall 3: Streamlit reruns re-trigger the download
**What goes wrong:** `if st.button("Install"): start_download(...)` re-fires across reruns; or the user clicks twice; multiple threads write the same `.part`.
**Why it happens:** Streamlit reruns the whole script on every interaction; button truthiness + an unguarded call body restarts work.
**How to avoid:** Track per-voice download state in `st.session_state.dl_state` and refuse to start a second thread when one is already in-flight for that voice id (Pattern 3). Optionally lock the `.part` (single-writer) by checking `dl_state` before spawning.
**Warning signs:** Garbled progress, doubled bytes, md5 mismatch under double-click.

### Pitfall 4: md5 mismatch handling deletes the wrong thing / loops
**What goes wrong:** On md5 mismatch, code renames anyway (installs corrupt), or deletes the `.part` and immediately auto-retries forever.
**How to avoid:** On mismatch, delete the `.part` (it is unrecoverable — a resumed-from-corruption file won't self-heal) and surface a clear error; let the user retry manually. Never `os.replace` a file that failed verification (Pattern 1).
**Warning signs:** A "Ready" voice that fails at synth time; infinite re-download.

### Pitfall 5: Uninstalling an in-use voice breaks an in-flight or future job (D-17)
**What goes wrong:** User deletes `en_US-amy-medium.onnx` while a pending job has `tts_voice="en_US-amy-medium"` or it's the saved per-engine default → synth fails.
**Why it happens:** No referential link between `app_settings`/`jobs.tts_voice` and the files on disk.
**How to avoid:** Before delete, block if the id equals (a) any non-terminal job's `tts_voice`, or (b) the value of any `tts.default_voice.<engine>` key in `app_settings`. Tell the user to switch first. Phase-3 `resolve_default_voice` is the backstop at selection time, but D-17 wants the protective up-front block.
**Warning signs:** Jobs failing with "Piper model not found" after an uninstall.

### Pitfall 6: Bundled curated manifest drifts from the live manifest
**What goes wrong:** A curated voice id in the bundled snapshot no longer exists upstream (renamed/removed) → download 404s.
**Why it happens:** The snapshot is frozen at build time; upstream changes.
**How to avoid:** "Refresh catalog" (D-02) re-fetches `voices.json`; treat a download 404 as a recoverable error ("This voice may have moved — try Refresh catalog"). Keep the curated subset small and on well-established voices (lessac, amy, ryan, alan, etc., which are long-stable). Pin a `voices.json` commit/etag in the snapshot for provenance.
**Warning signs:** 404 on a curated voice; manifest schema fields missing after a refresh.

### Pitfall 7: `file_uploader` size cap blocks Piper imports
**What goes wrong:** A `.onnx` is 60+ MB; Streamlit's default `maxUploadSize` is 200 MB but Diana's `5_Settings.py` lets the user set it (default written there). If set low, imports fail silently with a generic error.
**Why it happens:** `server.maxUploadSize` (MB) gates `file_uploader`; Diana writes it from the Settings "Max upload size" field.
**How to avoid:** Document that imports require `maxUploadSize` ≥ the largest expected `.onnx` (high-quality Piper voices can exceed 100 MB; medium ~63 MB). Validate the uploaded pair (both files present, names match base, `.onnx.json` parses) and show a clear message if rejected. The path-entry option (D-13) sidesteps the cap entirely for large local files.
**Warning signs:** "File too large" / truncated `.onnx` that fails md5 or load.

## Code Examples

### Manifest schema — representative Piper voice entry (VERIFIED live this session)
```json
// Source: https://huggingface.co/rhasspy/piper-voices/raw/main/voices.json (fetched this session)
"en_US-lessac-medium": {
  "key": "en_US-lessac-medium",
  "name": "lessac",
  "language": {
    "code": "en_US",
    "family": "en",
    "region": "US",
    "name_native": "English",
    "name_english": "English",
    "country_english": "United States"
  },
  "quality": "medium",
  "num_speakers": 1,
  "speaker_id_map": {},
  "files": {
    "en/en_US/lessac/medium/en_US-lessac-medium.onnx": {
      "size_bytes": 63201294,
      "md5_digest": "2fc642b535197b6305c7c8f92dc8b24f"
    },
    "en/en_US/lessac/medium/en_US-lessac-medium.onnx.json": {
      "size_bytes": 4885,
      "md5_digest": "c1f2b7bddefe113f3255ff9ef234cfd3"
    },
    "en/en_US/lessac/medium/MODEL_CARD": {
      "size_bytes": 351,
      "md5_digest": "42f2dd4a98149e12fc70b301d9579dfd"
    }
  },
  "aliases": ["en-us-lessac-medium"]
}
// Multi-speaker voices populate speaker_id_map, e.g. de_DE-thorsten_emotional-medium:
//   "speaker_id_map": {"amused":0,"angry":1,"disgusted":2,"drunk":3,
//                      "neutral":4,"sleepy":5,"surprised":6,"whisper":7}
```

### Raw download + sample URL patterns (VERIFIED live this session)
```text
# Model + config (each `files` key is the repo-relative path; prefix with resolve/main/):
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json

# Per-voice preview sample (D-12) — one MP3 per voice dir, named speaker_0.mp3 (~84 KB):
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/samples/speaker_0.mp3

# Kokoro model assets (GitHub release; verified content-length + 206 Range):
https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx      # ~310 MB (f32)
https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.fp16.onnx # ~169 MB
https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx # ~88 MB
https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin       # 28,214,398 bytes (~28 MB)
```
*Note: the URL `files` key already contains the full repo path (e.g. `en/en_US/lessac/medium/...`), so building the download URL is just `f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{path}"`. The sample lives at `<that voice dir>/samples/speaker_0.mp3`.*

### Typical Piper file sizes per quality tier
| Quality | `.onnx` size (typical) | Notes |
|---------|------------------------|-------|
| `x_low` | ~5–10 MB | 16 kHz, smallest |
| `low` | ~15–25 MB | |
| `medium` | ~50–65 MB | e.g. lessac-medium = 63.2 MB (verified) |
| `high` | ~90–125 MB | 22.05 kHz, largest; may exceed `file_uploader` cap |
*The `.onnx.json` config is always tiny (~4–6 KB). The disk-check should sum the `.onnx` + `.onnx.json` `size_bytes` from the manifest.*

### Settings restructure into tabs (D-09)
```python
# Source: streamlit st.tabs (standard API). Voices tab is the management hub.
tab_general, tab_voices, tab_processing, tab_llm, tab_news = st.tabs(
    ["General", "Voices", "Processing", "LLM Cleaning", "News"]
)
with tab_voices:
    # cross-engine browser (D-10) + Piper catalog (D-01) + import (D-13)
    # + install-state/footprint badges (D-11) + download/resume/cancel + uninstall (VOICE-07)
    ...
# NOTE: st.tabs renders ALL tab bodies on every run (they are not lazy). Keep the
# heavy/cached work (get_engine_voices is already @st.cache_data) so switching tabs is cheap.
```

### Storage shape for custom labels/tags (D-14) — recommended
```python
# Reuse app_settings(key, value). One JSON-valued key per voice id, namespaced.
# key:   "voice.labels.<engine>.<voice_id>"   value: JSON
# Example value:
# {"name": "My Amy", "language": "en-gb", "tier": "enhanced", "gender": "female",
#  "tags": ["audiobook", "calm"]}
import json
from diana.database import get_setting, set_setting

def get_label_overrides(db_path, engine, voice_id) -> dict:
    raw = get_setting(db_path, f"voice.labels.{engine}.{voice_id}", None)
    return json.loads(raw) if raw else {}

def set_label_overrides(db_path, engine, voice_id, overrides: dict) -> None:
    set_setting(db_path, f"voice.labels.{engine}.{voice_id}", json.dumps(overrides))

def apply_overrides(voice, overrides: dict):  # returns a new TTSVoice with overrides merged
    from dataclasses import replace
    merged = {k: overrides[k] for k in ("name", "language", "gender", "tier")
              if overrides.get(k)}
    return replace(voice, **merged)  # tags live alongside, surfaced to filter/search separately
```
*This keeps the merged result a plain `TTSVoice`, so the existing Phase-3 `filter_voices`/`order_by_quality` work unchanged. Custom tags are an extra field the browser indexes for search; since `TTSVoice` has no `tags` field, either (a) carry tags in a parallel dict keyed by id, or (b) extend `TTSVoice` with a defaulted `tags: tuple = ()` field (trailing-defaulted, mirroring how Phase 3 added `tier`/`bilingual` without breaking positional VOICES). Option (b) is cleaner and follows the established precedent.*

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Kokoro/Piper model "download" = a `wget` hint in a `FileNotFoundError` (`kokoro_engine.py:39,45`, `piper_engine.py:54`) | In-UI on-demand download into `model_dir()` via the generic layer | This phase (D-19) | Replaces the terminal/manual gap; no-terminal install (PROJECT constraint). |
| Manual `st.rerun()` loops for progress | `st.fragment(run_every=...)` | Streamlit 1.33+ (`st.fragment` stable); installed 1.56 | Periodic refresh without full-page rerun; cleaner background-task UX. |
| `os.statvfs` (POSIX) for free space | `shutil.disk_usage()` | stdlib (long stable) | Cross-platform (Windows) — required by Diana's Windows target. |

**Deprecated/outdated:**
- The `wget`-hint error messages in `kokoro_engine.py`/`piper_engine.py` are the gap this phase closes. (Note: 01-04 already corrected the *path* in the Kokoro hint to the per-user dir; this phase makes the download in-app.)
- `huggingface_hub` auto-download: not used (would add a heavy dep + its own cache; CONTEXT prefers `requests`).

## Runtime State Inventory

> Phase 4 is primarily greenfield (new download/cache layer + UI). It is NOT a rename/refactor. This section is included because the phase deletes files (uninstall/partial cleanup, VOICE-07) and writes durable state — the planner must know what runtime state the feature creates and removes.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `app_settings` gains new keys: custom labels/tags (`voice.labels.<engine>.<id>`), and optionally download/dismiss state. Existing `tts.default_voice.<engine>` keys (Phase 3) are read by the D-17 in-use check. | Code only — `set_setting`/`get_setting`; no schema migration (key/value table already exists). |
| Live service config | None — no external service config. The bundled curated manifest + samples ship as package data in the repo. | Ship `diana/data/piper_voices_curated.json` + `diana/data/samples/*.mp3` as package data (ensure `pyproject.toml` package-data/`MANIFEST.in` includes them for the Phase-6 build). |
| OS-registered state | None — no Task Scheduler/launchd/systemd. Downloads land as plain files in `paths.model_dir()`/`voices_dir()`. | None. |
| Secrets/env vars | None — HuggingFace + GitHub release assets are public, no auth/token needed (verified: anonymous curl succeeded). | None. |
| Build artifacts | Downloaded voice/model files in `model_dir()` are runtime artifacts (gitignored `data/`-equivalent in the per-user dir). `.part` files are transient and cleaned by VOICE-07's bulk action. | Bundled curated manifest/samples MUST be included in the PyInstaller/package build (Phase 6 dependency); flag for the packager. |

**Nothing found in categories:** OS-registered state and Secrets/env vars — verified None (public CDNs, no auth; no OS registration).

## Common Pitfalls — cross-platform (macOS now, Windows later)

This phase **ships on macOS** (per the objective). Windows-specific concerns to flag for the planner (and the deferred Windows UAT):
- `os.replace()` is atomic on Windows **only when src and dst are on the same volume** — they are (both in `model_dir()`), so fine. Flag: never `.part` in a temp dir on a different drive.
- `shutil.disk_usage()` works on Windows; pass a directory path (not a UNC root edge case). The ancestor-walk (Pattern 2) handles a not-yet-created `model_dir()`.
- Path separators: use `pathlib` throughout (already the repo norm) — the manifest `files` keys use `/`, which is fine for URL building but must be `Path(...)`-joined (not string-concatenated) for local paths.
- `file_uploader` and `maxUploadSize` behave identically; the size-cap pitfall (Pitfall 7) is platform-neutral.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Kokoro asset sizes for `kokoro-v1.0.onnx` (~310 MB f32) and `.int8.onnx` (~88 MB) are from the GitHub release page text (WebFetch); `voices-v1.0.bin` size (28,214,398 bytes) and Range support were curl-VERIFIED. | Code Examples / State of the Art | LOW — drives only the D-04 confirm-threshold copy and disk-check denominator; the downloader reads actual size from the stream/Content-Range at runtime anyway. The `.onnx` f32/int8 sizes are `[ASSUMED]` (page text, not curl); `voices-v1.0.bin` is `[VERIFIED]`. |
| A2 | The curated default subset (which Piper voices to feature) is unspecified — planner/discuss chooses. Suggested stable picks: en_US lessac/amy/ryan (medium), en_GB alan (medium), plus a few non-English best-per-language. | Pitfall 6 | LOW — purely a curation choice; "Show all" exposes everything regardless. |
| A3 | Whether to extend `TTSVoice` with a `tags: tuple = ()` field vs. a parallel tags dict is planner's choice. Recommendation: extend (mirrors Phase-3 `tier`/`bilingual` trailing-default precedent). | Storage shape | LOW — both work; extending is cleaner and precedented. |
| A4 | The size threshold for D-04 confirm (suggested >200 MB) is a discretion value; only Kokoro f32 (~310 MB) crosses it this phase (Piper voices and Kokoro int8 ~88 MB do not). | User Constraints (D-04) | LOW — tuning value; CONTEXT lists it as Claude's discretion. |
| A5 | `st.fragment(run_every="0.5s")` polling cadence is a suggested value; any sub-second-to-second value works. | Pattern 3 | LOW — UX tuning only. |

**Note:** The high-stakes external facts (manifest schema, URL patterns, Range/206 support, md5, disk_usage, PiperVoice.load convention) are all `[VERIFIED]` live this session — they are NOT assumptions. Only the items above remain genuinely open.

## Open Questions

1. **Which exact voices form the curated default subset?**
   - What we know: D-01 wants "curated best-per-language"; manifest has ~900+ voices; the long-stable English ones (lessac, amy, ryan, alan) are safe.
   - What's unclear: The full curated list and whether to bundle samples for all of them.
   - Recommendation: Planner picks a small set (≤~15) of stable, well-known voices; discuss-phase can confirm. "Show all" covers the rest, so this is low-risk.

2. **Extend `TTSVoice` with `tags` or keep a parallel structure?**
   - What we know: D-14 wants custom free-text tags feeding filters/search; `TTSVoice` currently has no tags field.
   - What's unclear: Which storage shape the planner prefers.
   - Recommendation: Extend `TTSVoice` with `tags: tuple = ()` (trailing-defaulted — exactly how Phase 3 added `tier`/`bilingual` without breaking the positional `VOICES` lists). Filter/search then read `tags` alongside `name`.

3. **Concurrent-download policy (serialize vs. parallel)?**
   - What we know: CONTEXT lists this as Claude's discretion; Piper voices are small.
   - What's unclear: Whether to allow multiple simultaneous installs.
   - Recommendation: Serialize (one in-flight download at a time) for the MVP — simpler progress UX, avoids bandwidth/`.part` contention; the `dl_state` dict already supports a "busy" guard.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `requests` | Download layer (ENGINE-02) | ✓ | 2.33.1 | — (stdlib `urllib` if ever removed) |
| `streamlit` | Voices-tab UI (D-09), `st.fragment` | ✓ | 1.56.0 | — |
| `piper-tts` | Live preview of installed Piper voices (VOICE-03) | ✓ | 1.4.2 | Binary fallback already in `piper_engine.py` |
| `kokoro-onnx` | Synth after Kokoro download (D-19) | ✓ | 0.5.0 | — |
| `hashlib`/`shutil`/`os`/`json`/`threading`/`tempfile`/`pathlib` | All core download/cache logic | ✓ | stdlib | — |
| Network access to `huggingface.co` | Piper catalog refresh + voice/sample download | ✓ (verified anonymous curl) | — | Bundled snapshot + curated samples work fully offline (D-02/D-12); only on-demand fetch needs network |
| Network access to `github.com` release assets | Kokoro model download (D-19) | ✓ (verified anonymous curl, 206 Range) | — | None — Kokoro download requires network (acceptable; it's an explicit user action) |
| `slopcheck` | Package legitimacy audit (research-time) | ✓ | installed | All deps pre-existing anyway |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** Network for on-demand fetch — the bundled curated manifest + samples provide full offline browse/preview (D-02/D-12); only the actual download of an uninstalled voice/model requires connectivity, which is an explicit user-initiated action.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7+ with `pytest-asyncio` (`asyncio_mode = "auto"`), per `pyproject.toml` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| Quick run command | `.venv/bin/python -m pytest tests/test_downloader.py tests/test_catalog.py -x` |
| Full suite command | `.venv/bin/python -m pytest tests/ -q` (currently 379 passed / 2 skipped) |

*All pytest/python runs MUST use the project `.venv` (per user memory: "Use .venv for Python work").*

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VOICE-01 | Manifest parse: build TTSVoice + footprint + URL from a `voices.json` entry | unit | `pytest tests/test_catalog.py::test_parse_manifest_entry -x` | ❌ Wave 0 |
| VOICE-01 | Curated-vs-show-all selection; group-by-language for show-all (D-03) | unit | `pytest tests/test_catalog.py::test_curated_subset -x` | ❌ Wave 0 |
| ENGINE-02 | Resume offset math: `.part` of size N → `Range: bytes=N-`; append on 206, reset on 200 | unit | `pytest tests/test_downloader.py::test_resume_offset -x` | ❌ Wave 0 |
| ENGINE-02 | md5 mismatch → `.part` deleted, no rename, raises | unit | `pytest tests/test_downloader.py::test_md5_mismatch_rejects -x` | ❌ Wave 0 |
| ENGINE-02 | md5 match → atomic `os.replace` to final | unit (tmp_path) | `pytest tests/test_downloader.py::test_atomic_finalize -x` | ❌ Wave 0 |
| ENGINE-02 / D-05 | Disk-check: free < needed*margin → refuse; ancestor-walk for missing dir | unit (monkeypatch `shutil.disk_usage`) | `pytest tests/test_downloader.py::test_disk_precheck -x` | ❌ Wave 0 |
| ENGINE-02 | Real network download of a tiny HF file resumes + verifies md5 | integration (network) | `pytest tests/test_downloader_net.py -m network` | ❌ Wave 0 (mark `network`, opt-in) |
| ENGINE-01 / D-11 | Install-state probe true/false from filesystem; footprint from manifest | unit (tmp_path) | `pytest tests/test_install_state.py -x` | ❌ Wave 0 |
| VOICE-04 / HARD-03 | Import filename validation: reject `../`, absolute, non-`.onnx`; accept the pair | unit | `pytest tests/test_voice_import.py::test_safe_dest -x` | ❌ Wave 0 |
| VOICE-06 / D-14 | Label override merge produces a TTSVoice the filters honor; tags searchable | unit | `pytest tests/test_voice_labels.py -x` | ❌ Wave 0 |
| VOICE-07 / D-17 | In-use block: id == job.tts_voice or a default key → refuse; else delete `.onnx`(+`.json`) | unit (tmp_path + in-mem db) | `pytest tests/test_uninstall.py -x` | ❌ Wave 0 |
| VOICE-07 / D-18 | Bulk partial cleanup globs `*.part` and removes them | unit (tmp_path) | `pytest tests/test_uninstall.py::test_clean_partials -x` | ❌ Wave 0 |
| D-03 (reuse) | Catalog filter/order via existing `filter_voices`/`order_by_quality` | unit (already covered) | `pytest tests/test_native_os_engine.py -x` | ✅ exists |
| ENGINE-04 / D-08 | Background progress UX, st.fragment polling, cancel/resume button | manual | (Streamlit UI — manual checklist) | n/a manual |
| VOICE-04 | `file_uploader` pair upload + maxUploadSize behavior | manual | (Streamlit UI — manual checklist) | n/a manual |
| VOICE-03 | Sample fetch+cache and live-synth preview audibly play | manual | (Streamlit UI — manual checklist) | n/a manual |
| D-09 | Settings st.tabs restructure renders; Voices tab is the hub | manual | (Streamlit UI — manual checklist) | n/a manual |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/test_downloader.py tests/test_catalog.py tests/test_install_state.py tests/test_voice_import.py tests/test_voice_labels.py tests/test_uninstall.py -x` (the pure-logic units — fast, no network).
- **Per wave merge:** `.venv/bin/python -m pytest tests/ -q` (full suite green; network-marked tests excluded by default).
- **Phase gate:** Full suite green + the manual Streamlit checklist (download/progress/cancel/resume, import pair, preview sample+live, tabs render, uninstall confirm+block) before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_downloader.py` — resume offset, 206-vs-200 append/reset, md5 reject/accept, atomic finalize, disk precheck (ENGINE-02, D-05/06/07)
- [ ] `tests/test_downloader_net.py` — opt-in `@pytest.mark.network` real-HF resumable download (ENGINE-02)
- [ ] `tests/test_catalog.py` — manifest parse, curated subset, footprint/URL build, group-by-language (VOICE-01, D-01/03)
- [ ] `tests/test_install_state.py` — Piper/Kokoro cheap probe + footprint (ENGINE-01, D-11)
- [ ] `tests/test_voice_import.py` — filename/traversal validation + pair check + metadata read (VOICE-04, HARD-03)
- [ ] `tests/test_voice_labels.py` — override merge + tag search feeding filters (VOICE-06, D-14)
- [ ] `tests/test_uninstall.py` — in-use block (D-17), delete pair, bulk `.part` cleanup (VOICE-07, D-18)
- [ ] Register `network` marker in `pyproject.toml` (`[tool.pytest.ini_options] markers = ["network: hits real endpoints"]`) so the opt-in download test doesn't warn.
- [ ] Add a Streamlit manual-UAT checklist doc (`04-*-MANUAL-UAT.md`) for the UI-only behaviors (ENGINE-04 progress/cancel/resume, file_uploader, preview, tabs, uninstall confirm).

*Test fixtures: a small `voices.json` excerpt fixture (2–3 entries incl. a multi-speaker one) under `tests/fixtures/`; a tiny real file for the opt-in network test (e.g. the 4885-byte `en_US-lessac-medium.onnx.json`).*

## Security Domain

> `security_enforcement` is not set in `.planning/config.json` (absent = enabled). This phase pulls files over the network and accepts user file uploads — security is materially relevant.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth in Diana (local single-user); CDNs are anonymous-public. |
| V3 Session Management | no | No sessions. |
| V4 Access Control | no | Single local user. |
| V5 Input Validation | **yes** | Validate uploaded/imported filenames (`os.path.basename` + resolved-prefix check, Pattern 5); validate manifest fields are well-typed before use; keep search/tag matching to plain substring (no user regex → no ReDoS). |
| V6 Cryptography | **yes (integrity, not secrecy)** | md5 verification of every downloaded file against the manifest `md5_digest` — integrity, not security crypto. (md5 is fine for accidental-corruption detection here; it is the digest the manifest ships.) |
| V12 File & Resources | **yes** | Downloads/imports land only under `model_dir()`/`voices_dir()`; `.part` + atomic rename prevents partial-file poisoning; uninstall deletes only within the cache dir; `file_uploader` size cap bounds memory. |
| V13/V14 (HTTPS / config) | **yes** | All download URLs are HTTPS (HF upgrades HTTP→HTTPS; GitHub release assets are HTTPS). `requests` verifies TLS by default — do not disable `verify`. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via crafted upload filename (`../../…`) | Tampering | `os.path.basename` + resolved-path-prefix check (reuse `1_Upload.py:268-284` guard); accept only `.onnx`/`.onnx.json`. (HARD-03.) |
| Zip-slip-style escape on import (absolute path entry) | Tampering | Same resolved-prefix check; reject absolute/`..` destinations. |
| Corrupt/poisoned download (MITM or truncation) installs a bad model | Tampering | md5 verify against manifest before `os.replace`; HTTPS + default TLS verification; delete `.part` on mismatch. |
| ReDoS via user free-text tags / name search | DoS | Plain substring `in` matching only (Phase-3 `_fold` approach) — never compile a user-supplied regex. |
| Disk-exhaustion from an unbounded download | DoS | D-05 universal pre-check refuses when free < needed*margin (Pattern 2). |
| Memory blow-up streaming a multi-GB file | DoS | `iter_content(chunk_size=64KB)` streaming write — never `r.content` for large files. |
| ScriptRunContext leak from a download thread calling `st.*` | (Streamlit-specific) Info disclosure / crash | Polling pattern — thread writes shared state only; `st.*` from the script thread (Pattern 3). |
| 404/renamed curated voice (availability) | DoS (feature) | "Refresh catalog" (D-02) + graceful 404 message; pin a manifest commit/etag. |

## Sources

### Primary (HIGH confidence — verified live this session)
- `https://huggingface.co/rhasspy/piper-voices/raw/main/voices.json` — manifest schema (key/name/language{}/quality/num_speakers/speaker_id_map/files{path:{size_bytes,md5_digest}}/aliases); representative + multi-speaker entries quoted.
- `https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/medium` and `.../samples` — file naming (`{key}.onnx`, `{key}.onnx.json`, `MODEL_CARD`, `samples/speaker_0.mp3` ~84 KB) and sizes.
- `https://huggingface.co/rhasspy/piper-voices/raw/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json` — config keys (language{}, audio.sample_rate/quality, dataset, num_speakers) for import metadata.
- Live `curl -I`/`-r 0-99` to HF `resolve/main/<path>` and GitHub `releases/download/...` — `307`/`302`→CDN, `accept-ranges: bytes`, `206 Partial Content` confirmed on both; `voices-v1.0.bin` content-length = 28,214,398.
- Live python (`.venv`) end-to-end test — resumable `Range` resume from a 1000-byte `.part`, `Content-Range: bytes 1000-4884/4885`, md5 match, `os.replace` success; `Content-Length: 0` pitfall on first GET observed.
- Live python — `shutil.disk_usage()` returns `(total, used, free)` on macOS; ancestor-walk for a missing target dir.
- `docs.streamlit.io/develop/concepts/design/multithreading` — official polling pattern; "do not call Streamlit commands from custom threads"; ScriptRunContext warnings quoted.
- Installed-version probes (`.venv`) — streamlit 1.56.0 (`st.fragment`/`st.status`/`st.progress` present), requests 2.33.1, piper-tts 1.4.2, kokoro-onnx 0.5.0.
- `slopcheck install requests streamlit piper-tts kokoro-onnx` — all 4 `[OK]` on PyPI.
- Diana source (read this session): `paths.py`, `tts/registry.py`, `tts/base.py`, `tts/piper_engine.py`, `tts/kokoro_engine.py`, `tts/native_os_engine.py`, `dashboard/pages/5_Settings.py`, `dashboard/pages/1_Upload.py`, `database.py`; `pyproject.toml` pytest config; `requirements.txt`.

### Secondary (MEDIUM confidence — verified with official source)
- `https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0` — Kokoro asset list + sizes (f32 ~310 MB, fp16 ~169 MB, int8 ~88 MB); `.bin` size + Range curl-verified, `.onnx` sizes from page text.
- WebSearch (k2-fsa sherpa docs, piper voice.py sources) cross-referenced with the live `.onnx.json` fetch — `PiperVoice.load(model)` defaults `config_path` to `{model}.onnx.json` (sibling convention).

### Tertiary (LOW confidence — flagged in Assumptions Log)
- Kokoro `.onnx` f32/int8 byte sizes (page text, not curl) — A1; non-load-bearing (runtime reads actual size).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all four libs already installed/pinned; no new dep; slopcheck clean.
- Manifest schema + URLs + Range/resume: HIGH — fetched and exercised live against the real endpoints this session.
- Architecture / integration points: HIGH — grounded in the actual Diana source read this session (registry, engines, paths, database, pages).
- Streamlit background-download pattern: HIGH — official docs + installed `st.fragment` confirmed.
- Pitfalls: HIGH — the two highest-risk ones (HF Content-Length=0; Range-ignored append corruption) were reproduced/handled live.
- Curated subset / tags shape / threshold values: open (LOW-stakes discretion) — see Assumptions Log + Open Questions.

**Research date:** 2026-06-15
**Valid until:** ~2026-07-15 (30 days; stable — manifest/CDN/stdlib/Streamlit APIs are slow-moving). Re-verify the curated manifest snapshot's voice ids before shipping if more than a few weeks elapse (Pitfall 6).

## RESEARCH COMPLETE
