---
phase: 04-engine-management-voice-catalog
plan: 02
subsystem: downloads-catalog
tags: [downloader, requests, resumable, md5, disk-check, piper-voices, manifest, install-state, package-data, ttsvoice]

# Dependency graph
requires:
  - phase: 04-engine-management-voice-catalog
    plan: 01
    provides: "TTSVoice.tags trailing-default; voices_manifest.json fixture; network pytest marker; 7 Wave-0 skipif scaffolds (downloader/catalog/install_state flip live here)"
  - phase: 03-native-os-tts-new-default
    provides: "native_voices_macos.py pure-helper + thin-wrapper shape; en_US->en-us language fold; filter_voices/order_by_quality reuse (D-03)"
  - phase: 01-foundation-privacy-toggle
    provides: "paths.model_dir()/voices_dir() per-user resolver (platformdirs)"
provides:
  - "diana/downloads/downloader.py — engine-agnostic resumable download (Range -> .part -> md5 -> os.replace), has_space disk pre-check (D-05), clean_partials bulk *.part cleanup (D-18); stdlib + requests only, import-clean of piper/kokoro/streamlit"
  - "diana/tts/catalog.py — parse_manifest (JSON->TTSVoice) + voice_footprint_bytes + download_url + load_bundled_manifest (offline, D-02) + refresh_catalog (only network touch, degrades gracefully) + curated_subset (D-01) + group_by_language (D-03)"
  - "diana/tts/install_state.py — cheap filesystem probes (ENGINE-01): piper_voice_installed, piper_footprint_bytes, kokoro_model_installed; no heavy SDK import"
  - "diana/data/piper_voices_curated.json — 9 verified best-per-language Piper voices (7 langs) + pinned upstream provenance commit"
  - "pyproject.toml [tool.setuptools.package-data] (data/*.json + data/samples/*) + addopts '-m not network' default-excluding the opt-in network smoke"
affects: [04-03 walking-slice download UI + badges, 04-04 import+uninstall (reuses clean_partials/install_state), 04-06 cross-engine browser + Kokoro download reuse]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Resumable download substrate: .part append-on-206 / reset-on-200, Content-Range/manifest size over Content-Length=0, md5-verify-before-atomic-os.replace, iter_content(64KB) streaming"
    - "Pure parser + thin I/O wrapper (native_voices_macos shape) for the catalog; refresh degrades to the bundled snapshot, never crashes"
    - "Cheap no-heavy-import filesystem probe lane (engine_is_ascii_only precedent) for install-state badges"

key-files:
  created:
    - diana/downloads/__init__.py
    - diana/downloads/downloader.py
    - diana/tts/catalog.py
    - diana/tts/install_state.py
    - diana/data/__init__.py
    - diana/data/piper_voices_curated.json
  modified:
    - pyproject.toml

key-decisions:
  - "Curated snapshot = 9 best-per-language voices fetched VERBATIM from the live rhasspy/piper-voices manifest at implementation time (verified size_bytes + md5_digest), wrapped {_provenance, voices} with the upstream commit pinned (Pitfall 6) — no hand-transcribed digests"
  - "download_url named per the binding Wave-0 scaffold probe (build_download_url|download_url|voice_download_url), not the plan-interface's download_url_for — the scaffold is the contract"
  - "clean_partials(directory=None) defaults to paths.model_dir() (lazy import) so the D-18 bulk action is a zero-arg call — matches the Plan-04 test_uninstall::test_clean_partials scaffold that bound to it"
  - "addopts '-m not network' added to pyproject so the opt-in network smoke is excluded by default (the 04-01 marker registered the name but nothing deselected it; landing download_file un-skipped the live-HF test)"
  - "piper_footprint_bytes returns 0 when not installed (matches the single-arg scaffold), not the manifest size_bytes from the plan prose — the not-installed estimate is resolved at the call site via catalog.voice_footprint_bytes"

requirements-completed: [ENGINE-01, ENGINE-02, VOICE-01]

# Metrics
duration: ~7min
completed: 2026-06-15
---

# Phase 4 Plan 02: Generic Download/Cache Substrate + Piper Catalog Data Layer Summary

**The engine-agnostic resumable downloader (Range -> `.part` -> md5 -> atomic `os.replace`, disk pre-check, bulk partial cleanup), the Piper manifest parser/curator with a verified bundled snapshot + on-demand refresh, and the cheap no-heavy-import install-state probe — all Streamlit-free, import-clean of every engine SDK, and proven by the Wave-0 scaffolds flipping to live (suite 391 passed / 6 skipped / 1 deselected).**

## Performance

- **Duration:** ~7 min implementation (2 atomic task commits, 13:46 -> 13:50 local)
- **Tasks:** 2 (both `tdd="true"`; RED lived in the Wave-0 04-01 scaffolds, GREEN landed here)
- **Files:** 7 (6 created + 1 modified)

## Accomplishments
- **ENGINE-02 resumable downloader** (`diana/downloads/downloader.py`): `download_file` copies RESEARCH Pattern 1 verbatim — resume via `Range` (206 appends, 200 resets the `.part`), total from manifest `size_bytes`/`Content-Range` never a zero `Content-Length`, `iter_content(64KB)` streaming, md5 verify of the completed `.part` with delete-on-mismatch, atomic `os.replace` only on a verified file, cancel leaves the `.part` for resume.
- **D-05 universal disk pre-check**: `has_space` (RESEARCH Pattern 2 verbatim) walks up to the first existing ancestor of a not-yet-created `model_dir()` and refuses when `free < needed*margin`.
- **D-18 partial cleanup**: `clean_partials` globs `*.part` and `unlink(missing_ok=True)`, defaulting to `model_dir()` for the zero-arg bulk action.
- **VOICE-01 catalog** (`diana/tts/catalog.py`): pure `parse_manifest` (JSON -> `TTSVoice`, `en_US->en-us` fold, `quality->tier`, malformed entries skipped), `voice_footprint_bytes` (sum `.onnx` + `.onnx.json`), `download_url`, offline `load_bundled_manifest` (D-02), `refresh_catalog` (the only network touch; degrades to the bundled snapshot on any failure with a `%`-style warning), `curated_subset` (D-01 best-per-language flat view), `group_by_language` (D-03 collapsible show-all).
- **ENGINE-01 cheap install-state** (`diana/tts/install_state.py`): `piper_voice_installed`, `piper_footprint_bytes`, `kokoro_model_installed` — filesystem probes of `model_dir()` with no `onnxruntime`/`piper`/`kokoro` import.
- **Bundled data + package-data**: `diana/data/piper_voices_curated.json` (9 verified best-per-language voices across en_US/en_GB/de/fr/es/it/nl, provenance commit pinned); `pyproject.toml` gains `[tool.setuptools.package-data]` (`data/*.json` + `data/samples/*`) and `[tool.setuptools.packages.find]`.
- **Scaffolds flipped live**: `tests/test_downloader.py` (5), `tests/test_catalog.py` (parse + curated), `tests/test_install_state.py` (3), and the Plan-04 `test_uninstall::test_clean_partials` all moved SKIPPED -> GREEN with zero test edits. Full suite **391 passed / 6 skipped / 1 deselected** (baseline 380/18; +11 flipped live, network test now deselected, 6 remaining skips are Plan 04/05 scaffolds).

## Task Commits

Each task committed atomically (authored solely as tfm000, no AI co-author):

1. **Task 1: Generic resumable downloader + disk-check + partial cleanup** — `f18b18e` (feat)
2. **Task 2: Piper catalog + cheap install-state + bundled snapshot + package-data** — `9782c8b` (feat)

**Plan metadata:** (this commit) — docs: complete plan

## Files Created/Modified
- `diana/downloads/__init__.py` — empty package marker (mirrors `diana/tts/__init__.py`).
- `diana/downloads/downloader.py` — `download_file` / `has_space` / `clean_partials`; stdlib + `requests` only; lazy `diana.paths` import inside `clean_partials`; import-clean of piper/kokoro/streamlit.
- `diana/tts/catalog.py` — pure `parse_manifest` + footprint/URL helpers + `load_bundled_manifest`/`refresh_catalog` + `curated_subset`/`group_by_language`; import-clean of every engine SDK.
- `diana/tts/install_state.py` — cheap `model_dir()` probes; imports only `diana.paths`.
- `diana/data/__init__.py` — package marker so the data dir ships.
- `diana/data/piper_voices_curated.json` — `{_provenance, voices}`; 9 verified entries; upstream commit `b710b0ba…` pinned (last_modified 2026-05-15).
- `pyproject.toml` — `[tool.setuptools.package-data]` + `[tool.setuptools.packages.find]` + `addopts = "-m 'not network'"`.

## Decisions Made
- **Verified curated snapshot, fetched at implementation time.** The plan permitted filling non-English picks from the live manifest. All 9 voices (lessac/amy/ryan/alan + de/fr/es/it/nl) were pulled verbatim from the live `voices.json` with their real `size_bytes` + `md5_digest` — no invented digests (which would 404/mismatch at download time). Provenance commit pinned per Pitfall 6.
- **`download_url` over the plan's `download_url_for`.** The binding Wave-0 scaffold probes `build_download_url|download_url|voice_download_url`; `download_url_for` would not bind. The scaffold is the contract, so the function is named `download_url`.
- **`clean_partials(directory=None)` defaults to `model_dir()`.** The Plan-04 `test_uninstall::test_clean_partials` scaffold bound to my `clean_partials` (Task 1's symbol) and calls it zero-arg. Making `directory` optional (lazy `paths` import) satisfies the D-18 bulk-cleanup contract while keeping the explicit-directory primitive.
- **`piper_footprint_bytes` returns 0 when not installed.** The single-arg scaffold asserts `== 0` for an absent voice; the not-installed manifest-size estimate is the call site's job (`catalog.voice_footprint_bytes`), keeping this probe a cheap filesystem read.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Network smoke ran in the default suite**
- **Found during:** Task 2 full-suite verification.
- **Issue:** `tests/test_downloader_net.py` is `@pytest.mark.network` and documented "excluded by default", but 04-01 only *registered* the marker — nothing deselected it. Landing `download_file` flipped the test's `skipif` to active, so the default `pytest` run hit live HuggingFace (and failed on a seeded-`.part` md5).
- **Fix:** Added `addopts = "-m 'not network'"` to `[tool.pytest.ini_options]`. Default runs deselect it; `-m network` still opts in (verified: `1 deselected` by default, `1 test collected` under `-m network`).
- **Files modified:** `pyproject.toml`
- **Commit:** `9782c8b`

**2. [Rule 1 - Bug] `clean_partials` could not satisfy the zero-arg D-18 contract**
- **Found during:** Task 2 full-suite verification.
- **Issue:** Task 1 shipped `clean_partials(directory)` (required arg); the Plan-04 `test_clean_partials` scaffold bound to it and calls `clean_partials()` expecting a `model_dir()` default — `TypeError: missing 1 required positional argument`.
- **Fix:** `directory` now defaults to `None` -> `paths.model_dir()` via a lazy import (keeps the module's top-of-file import surface minimal; `diana.paths` pulls no engine SDK).
- **Files modified:** `diana/downloads/downloader.py`
- **Commit:** `9782c8b`

Both fixes are in scope: they were caused directly by this plan's new symbols un-skipping Wave-0/Plan-04 scaffolds, and both were resolved within the fix-attempt budget on the first attempt.

## Known Stubs
None. Every shipped symbol is fully implemented and exercised by a live test. `diana/data/samples/*` (the bundled preview clips) is intentionally NOT created here — it is Plan 04's deliverable; the `package-data` glob is declared ahead of it so no later pyproject edit is needed.

## Threat Flags
None. No new trust boundary beyond the ones in the plan's `<threat_model>`: HTTPS-only download (default TLS verification, never `verify=False`), md5 integrity verify before install, disk-exhaustion pre-check, streaming write (no `r.content`), and graceful manifest-refresh degradation are all implemented as specified.

## Packaging Flag (Phase 6)
`diana/data/piper_voices_curated.json` (and the future `diana/data/samples/*` from Plan 04) ship via `[tool.setuptools.package-data]`. **The Phase-6 packager MUST verify these land in the PyInstaller bundle** (RESEARCH Runtime State Inventory) — `package-data` covers a `pip`/`setuptools` build but PyInstaller needs its own `datas`/`--add-data` entry.

## Issues Encountered
None beyond the two in-scope auto-fixes above. The bundled-snapshot `.onnx` + `.onnx.json` footprint for lessac (63201294 + 4885 = 63206179) matches the fixture, confirming schema consistency between the committed fixture and the live-fetched curated set.

## User Setup Required
None. The catalog browses fully offline from the bundled snapshot; only an explicit "Refresh catalog" or an on-demand voice download touches the network (public, anonymous CDNs — no keys).

## Next Phase Readiness
- **Plan 03 (walking slice):** drives `download_file` + `has_space` + the catalog from a Voices-tab UI thread (RESEARCH Pattern 3) and renders `install_state` badges — all the load-bearing correctness is unit-proven here.
- **Plan 04 (import + uninstall):** reuses `clean_partials` (D-18, already live) and the `install_state` probes; `safe_voice_dest` + the in-use predicate remain its scaffolds.
- **Plan 06 (cross-engine browser + Kokoro download):** reuses `download_file` for the Kokoro model (the URLs are in RESEARCH) and the catalog/curation helpers; `kokoro_model_installed` already gates the engine-level badge.
- No blockers.

## Self-Check: PASSED

All 6 created files + the `pyproject.toml` package-data edit verified present on disk; both task commits (`f18b18e`, `9782c8b`) verified in git history.

---
*Phase: 04-engine-management-voice-catalog*
*Completed: 2026-06-15*
