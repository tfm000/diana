---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed Phase 04 Plan 03 (walking slice — Settings st.tabs + Voices hub; one Piper voice installs end-to-end and is selectable; human-verify APPROVED)
last_updated: "2026-06-15T15:00:41.000Z"
last_activity: 2026-06-15 -- Completed Phase 04 Plan 03 (walking slice: tabbed Settings + Voices hub + one-Piper-voice threaded install -> selectable)
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 19
  completed_plans: 16
  percent: 84
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-29)

**Core value:** Convert documents into listenable audiobooks entirely on-device — so even private or sensitive files can be turned into audio without sending them anywhere.
**Current focus:** Phase 04 — engine-management-voice-catalog

## Current Position

Phase: 04 (engine-management-voice-catalog) — EXECUTING
Plan: 4 of 6
Status: Executing Phase 04 (04-01 + 04-02 + 04-03 complete; Wave 3 walking slice landed — tabbed Settings + one-Piper-voice install proven end-to-end through the UI)
Last activity: 2026-06-15 -- Completed Phase 04 Plan 03 (walking slice: tabbed Settings + Voices hub + one-Piper-voice threaded install -> selectable)

Progress: [████████░░] 84% (16/19 plans complete; Phase 04 walking slice landed — substrate proven end-to-end through the real UI against the real network)

## Performance Metrics

**Velocity:**

- Total plans completed: 16
- Average duration: ~5 min implementation (plus blocking human-verify checkpoint gaps)
- Total execution time: ~1.3 hours active

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 01 | 4/4 | ~57min wall impl (incl. deviation tweaks; excludes checkpoint gaps) | ~4min impl |
| 01 | 4 | - | - |

**Recent Trend:**

- Last 5 plans: 03-04 (~9min impl, wall ~25h spanning blocking human-verify, 1 deviation), 03-05 (~4min impl, Task 3 Windows UAT deferred), 04-01 (~9min, 0 deviations), 04-02 (~7min), 04-03 (~58min impl, wall ~1h spanning blocking human-verify, 3 in-plan deviations)
- Trend: 04-03 was the most deviation-heavy plan to date — 3 Rule-1 integration bugs surfaced at the blocking human-verify checkpoint (Resume terminal-state, Piper install→use enumeration, no-restart cache + uniform names), all fixed in-plan and re-verified. Consistent with the Phase-1/3 pattern that integration/UX defects surface at human-verify, not during autonomous impl; the higher count reflects the first-of-its-kind thread+st.fragment pattern (no in-repo precedent) meeting the real install→use→display flow. Deviation #2 was deliberately built as the shared enumeration foundation 04-05 reuses (no duplication).

*Updated after each plan completion*
| Phase 01 P02 | ~24min | 3 tasks | 8 files |
| Phase 01 P03 | ~3min impl (wall ~26h spanning checkpoint) | 4 tasks (3 auto + 1 blocking checkpoint) | 7 files (6 planned + 1 scope-expansion via deviation #1) |
| Phase 01 P04 | ~5min impl (wall ~14h spanning checkpoint) | 3 tasks (2 auto + 1 blocking checkpoint) | 3 files (matches plan files_modified exactly; +1 unrelated Kokoro-paths fix attributed to 01-01, not counted here) |
| Phase 02 P01 | 9min | 3 tasks | 19 files |
| Phase 02 P02 | 4min | 2 tasks | 13 files |
| Phase 02 P03 | 5min | 2 tasks | 7 files |
| Phase 02 P04 | 13min | 3 tasks | 9 files |
| Phase 03 P01 | 4min | 3 tasks | 4 files |
| Phase 03 P02 | 2min | 2 tasks | 2 files |
| Phase 03 P03 | 3min | 3 tasks | 6 files |
| Phase 03 P04 | ~9min impl (wall ~25h spanning blocking human-verify) | 2 tasks (1 auto/TDD + 1 blocking checkpoint) | 5 files (4 planned + diana/tts/registry.py; +1 in-plan deviation = empty-filter crash fix 7be54ac) |
| Phase 03 P05 | ~4min impl | 2 of 3 tasks (2 auto/TDD; Task 3 blocking Windows UAT DEFERRED, not blocked) | 4 files (3 planned modified + 1 deferred-UAT created; matches files_modified; no scope expansion) |
| Phase 04 P01 | ~9min | 3 tasks (3 auto; zero deviations) | 10 files (8 created: 7 scaffolds + manifest fixture; 2 modified: base.py + pyproject.toml — matches files_modified) |
| Phase 04 P04-02 | ~7min | 2 tasks | 7 files |
| Phase 04 P03 | ~58min impl (wall ~1h spanning blocking human-verify) | 2 tasks (1 auto + 1 blocking checkpoint; checkpoint surfaced 3 in-plan Rule-1 deviations) | 9 files (plan named only 5_Settings.py; effective set = 5_Settings.py + 1_Upload.py + voice_cache.py[new] + registry.py + install_state.py + catalog.py + 3 new test files) |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 04 plan 01]: TTSVoice extended with a trailing-defaulted `tags: tuple[str, ...] = ()` field (A3/D-14) — chosen over a parallel dict, mirroring the Phase-3 tier/bilingual precedent so the 5 piper + 9 kokoro 4-arg positional VOICES lists stay valid with zero edits. This is the one shared contract Plan 05's voice_labels layer and Plan 06's cross-engine browser build on; landed in Wave 0 so it exists before either is built.
- [Phase 04 plan 01]: Wave-0 scaffold pattern reaffirmed (same as 03-01) — 7 test files (downloader/downloader_net/catalog/install_state/voice_import/voice_labels/uninstall) are guarded-import + skipif with REAL assertion bodies (never `pass`/xfail) so collection stays green now and each flips to a live regression gate when its symbol lands in Plans 02/04/05 — no later test-file edits. Planner's-choice symbols (downloader/catalog/install_state/voice_labels module homes; the in-use predicate's arity) are bound via multi-candidate import-probe loops + inspect.signature tolerance.
- [Phase 04 plan 01]: The HARD-03 import-traversal scaffold (test_voice_import) asserts the security INVARIANT — resolved dest stays contained within model_dir + a .onnx/.onnx.json extension allow-list raises — rather than mandating a raise on `../`, because RESEARCH Pattern 5's reference safe_voice_dest applies os.path.basename first (neutralizing traversal). The scaffold therefore binds whether Plan 04 strips-and-contains or rejects-outright. Live baseline this session was 379 passed / 0 skipped (the planning-doc "2 skipped" had already flipped live in 03-05); post-plan 380 passed / 18 skipped — no regression.

- [Roadmap]: Structure = vertical slices in dependency order (brownfield; infra exists; each phase ships a usable capability)
- [Roadmap]: Foundation (RETIRE-01 + PLAT-01) ships first — gates on-demand downloads and packaging
- [Roadmap]: Favor clean breaking changes over backward-compat shims — no existing user base
- [Roadmap]: PLAT-02 (first-class Windows) grouped with packaging (Phase 6) where the Windows CI runner verifies it
- [Phase 1 plan]: 4 plans sequenced into 4 waves (1→2→3→4) because they share config.py/database.py/1_Upload.py — sequential to avoid same-file write conflicts; each plan is a complete user-visible vertical slice
- [Phase 1 plan]: Durable per-page LLM toggle persisted in a new SQLite app_settings(key,value) table (Claude's Discretion D-07/D-10) — survives restart, UI-only, sidesteps the load-once config singleton
- [Phase 1 plan]: 4_Web.py decorative-toggle reconciliation (RESEARCH A2) deferred — explicitly outside the named PRIV-01..04 (Upload + News only) scope
- [Phase 01]: Per-user storage via single platformdirs resolver (diana/paths.py, appauthor=False); no data migration (D-01), config seeded fresh in per-user dir (D-02), all paths from one resolver (D-03) — satisfies PLAT-01
- [Phase 01 plan 02]: Cloud TTS retired (RETIRE-01) via clean break (D-04, no shim). Stale-engine handling falls back to kokoro SILENTLY — guarded picker + logger.warning, no in-UI notice (D-05 amended by user during verification); saved config never auto-rewritten.
- [Phase 01 plan 03]: PRIV-04 gate enforced at the pipeline branch itself, not just in the UI — `if want_llm and llm_cfg is not None: llm_clean_text else clean_text`. UI disabled state and pipeline gate are independent layers; either alone would be insufficient (proven by `test_no_provider_forces_rule_based`).
- [Phase 01 plan 03]: `Job.use_llm` is `Optional[bool]` with a nullable `jobs.use_llm INTEGER` migration (NO default) so existing in-flight rows keep "no per-job choice -> legacy global" (T-03-02 mitigation; RESEARCH Pattern 4 anti-pattern).
- [Phase 01 plan 03, scope expansion during verify]: Added a Settings LLM-active status indicator (`diana/dashboard/pages/5_Settings.py`) mirroring `get_llm_config` so Settings and Upload/News agree on what "configured" means. `5_Settings.py` is therefore part of 01-03's effective files_modified set even though the plan frontmatter did not list it — recorded as deviation #1 (Rule 2 missing-critical) plus deviation #2 (Rule 1 UX bug repositioning). Both approved as in-scope because they harden the PRIV-04 gate UX-side; not deferred.
- [Phase 01 plan 04]: PRIV-04 fully closed across both surfaces — combined with 01-03's Upload-half, the toggle is disabled-with-explanation when no provider AND with LLM off, News converts cleaned raw article text to audio instead of summarizing. The OFF policy is enforced at the same pipeline branch from 01-03 (`if want_llm and llm_cfg is not None: llm_clean_text else clean_text`) because the digest job carries `use_llm=False`; the page's `build_digest_text` is a pure Streamlit-free helper so PRIV-04 / D-09 is unit-testable without spinning up Streamlit or the network.
- [Phase 01 plan 04]: Privacy-default UX rule established — when a provider is configured the LLM-ON branch is enabled; when no provider is configured the toggle is disabled BUT the "Build News Digest" button stays active. Losing the LLM must NOT lose the feature on a privacy-first product. Pattern applies to any future LLM-dependent surface (e.g. Phase 4 voice catalog blurbs, Phase 5 heavy-engine status).
- [Phase 01 plan 04, related fix attributed to 01-01]: Kokoro engine "model/voices not found" error messages still suggested `wget -P data/models/` even though PLAT-01 had routed `KokoroConfig.model_path`/`voices_path` through the platformdirs resolver — i.e. the message *said* "not found at `~/Library/Application Support/Diana/models/...`" but *told the user* to download to the old repo-local path. Fixed by interpolating `{model.parent}` / `{voices.parent}` into the wget target (commit b8e70d0). Bug originated in 01-01's `KokoroConfig` path routing (a862642 / 31dcd37) — 01-04 only surfaced it via the first real digest worker run. Commit subject is `fix(01-01): ...` so the audit trail attributes the work to PLAT-01, not to PRIV-02/04; `diana/tts/kokoro_engine.py` is NOT counted in 01-04's `files_modified` set.
- [Phase 02]: clean_text widened to keyword-only (text, *, source_format=None, ascii_only=False) — clean break, no shim; default ascii_only=False (non-destructive); engine capability resolved at the pipeline call site via engine_is_ascii_only so cleaner.py stays diana.tts-free
- [Phase 02]: chart-fragment removal requires a >=3 noise cluster to contain a short LABEL (refinement beyond RESEARCH's numeric-fraction predicate) so label-less year/number lists are preserved — keeps both X-axis-cluster removal and year-list preservation green
- [Phase 02]: Wave-1 corpus invariants assert only preservation + basic structural; URL/email (02-03) and figure/footnote (02-04) removal invariants deferred to a documented '_invariants Wave N adds' extension point so later slices append their invariant as the stage lands
- [Phase 02 plan 02]: Currency/percent symbol→word (_normalize_currency_percent) runs BEFORE the math-aware _remove_inline_math — the phase's load-bearing ordering: converting currency removes every $ first so "$5 and $10" both survive (the math-signal guard alone still destroys it because the inner "5 and " matches the signal). Digits are never spelled to words (no number-to-words; VNEXT-03 stays deferred).
- [Phase 02 plan 02]: The buggy bare `re.sub(r"\$[^$]*?\$", "")` is replaced by a math-aware _remove_inline_math over a bounded module-level _INLINE_MATH_RE = re.compile(r"\$([^$\n]{1,200}?)\$") (ReDoS mitigation T-02-01; verified linear on 100k adversarial $-input). Stray-command/brace stripping was folded into the new helper so the LaTeX test classes stay green.
- [Phase 02 plan 02]: Curated low-ambiguity _ABBREVIATIONS only (Dr./Mr./Mrs./Ms./Prof./e.g./i.e./etc./vs./approx./cf.); a (?<![A-Za-z]) lookbehind + the required trailing period prevent mid-word (Drone. stays) and bare-token (the word "Mr" stays) false matches. Ambiguous m/kg/St. are deferred to the engine. Expansion runs BEFORE URL stripping so dotted tokens (e.g./U.S.) are already words for 02-03.
- [Phase 02 plan 02]: Per the incremental corpus contract, 5 normalization fixtures were added and run through the existing Wave-2 _invariants (cross-stage), but NO new removal invariant was registered — currency/abbreviation are transforms; no-URL/email stays 02-03, figure-token stays 02-04. Regression #3 flipped (95% → "95 percent").
- [Phase 02 plan 03]: Code-block removal (_remove_code_blocks: fenced bounded-DOTALL span + contiguous 2+ line indented runs) runs BEFORE table/chart detection so short symbol-heavy code lines do not false-trigger the noise detectors; a SINGLE indented line is KEPT (CLEAN-07 over-strip guard — a lone indented line is prose, not code). Noise-detector tests (ChartFragments/TableRemoval) stayed green, proving the code-before-noise ordering did not regress them.
- [Phase 02 plan 03]: _strip_list_markers (- / * / + / 1. / a)) runs AFTER _remove_chart_fragments so the 02-01 chart/heading protection still sees the markers; the line is never deleted, only the marker prefix is stripped and the item prose kept.
- [Phase 02 plan 03]: URL (http(s)+www.) and email removal use a STRUCTURAL guard — required scheme/www. prefix and required @ — so U.S./e.g. survive without a denylist; removed entirely (no "link" token, Decision 4). The no-URL/no-email removal invariant is REGISTERED into the corpus _invariants this wave (the wave that owns it) and holds across all snapshots; the figure-token invariant stays deferred to 02-04. CLEAN-05 satisfied.
- [Phase ?]: [Phase 02 plan 04]: _handle_captions_and_refs replaces the blunt _remove_figure_table_refs — captions (label at a segment boundary + ':'/'.' + capitalized prose) keep the sentence with only the label+delimiter dropped; inline references are removed (whole cross-reference parentheticals first, then bare tokens) then _repair_dangling fixes the grammar. CLEAN-01 satisfied.
- [Phase ?]: [Phase 02 plan 04]: _repair_dangling whitespace quantifiers are BOUNDED ({0,8}/{1,8}) — the unbounded form was O(n^2) under re.sub on adversarial space runs (36s/9s observed and fixed mid-task, Rule-1). The non-spec ' .'->'.' substitution was dropped. ReDoS T-02-01 is now runtime-verified linear for the figure/caption/footnote stages.
- [Phase ?]: [Phase 02 plan 04]: Footnote markers always (superscript U+00B9/B2/B3 + U+2070-2079 removed for ALL engines in _remove_citations); footnote BODIES best-effort (_remove_footnote_bodies drops a conservative 20+-char marker-prefixed capitalized block after a blank line, all-lines-match, at stage 6). The 20+-char gate keeps a short numbered list intact. CLEAN-03 satisfied, honestly scoped.
- [Phase ?]: [Phase 02 plan 04]: Final no-figure-token removal invariant REGISTERED into the corpus _invariants (completing the removal set) across all 15 snapshots; a complete-stage-ordering source-index test pins every hard constraint; an EPUB/UTF-8 fixture extends coverage to all PDF/EPUB/TXT flavors; the planted-regression check turned the corpus RED with a legible diff and restored green. CLEAN-08 demonstrated (ROADMAP criterion #4).
- [Phase ?]: [Phase 03 plan 01]: Wave-0 scaffold pattern = import-guard future symbols + skipif-gate dependent tests with real assertion bodies (NOT xfail) so collection stays green now and each test auto-flips to a live regression gate when its symbol lands in Plans 02-05 — no later test-file edits. Scaffolds probe multiple candidate module homes for planner's-choice symbols (filter_voices, the D-03 resolver).
- [Phase ?]: [Phase 03 plan 01]: pytest-asyncio installed (1.4.0) + asyncio_mode='auto' in pyproject — removes the Phase-1 deferred async-test blocker (test_anthropic_cli_real_call now runs). KNOWN expected breaks deferred to Plan 03 (same wave that causes them): test_tts_registry::test_unknown_engine_defaults_ascii_only + test_local_only, and test_config default assertions, flip once native_os registers (_ASCII_ONLY=False, list_engines includes native_os, config default engine to native_os / voice to empty).
- [Phase 03]: [Phase 03 plan 02]: TTSVoice extended with trailing-defaulted tier + bilingual fields (D-05) so kokoro/piper 4-arg positional VOICES stay valid with zero edits; optional default_voice() Protocol method deferred to Plan 03 with the engine
- [Phase 03]: [Phase 03 plan 02]: macOS say -v '?' parsed via locale-anchored _SAY_LINE regex (never .split() — handles nested-parenthetical and non-ASCII names); pure parse_say_voices(text) seam is fixture-testable, enumerate_macos_voices() shells say via list-argv subprocess.run timeout=15 (T-03-03/04, V5)
- [Phase 03]: [Phase 03 plan 02]: quality tier prelabelled from curated _NOVELTY/_ENHANCED sets (D-06) with compact fallback; gender='unknown' (say does not expose it). Both tdd=true tasks satisfied via Wave-0 03-01 scaffolds flipping skip->pass (RED is in the prior wave's git history); known native_os registry/config-default breaks remain Plan 03's to own
- [Phase ?]: [Phase 03 plan 03]: NativeOSEngine = ONE class with internal sys.platform branch (not two engines); macOS _say_synth shells list-argv say -o --data-format=LEI16@22050 with text as the FINAL argv element (V5), tempfile+finally-unlink (V12), timeout=300; empty voice id => OS system default (D-02). WinRT methods stubbed NotImplementedError, marked for Plan 05, so the macOS path is complete + importable on a Mac with no winrt (no module-top winrt import).
- [Phase ?]: [Phase 03 plan 03]: get_engine_voices('native_os') is the DYNAMIC branch (D-04) — constructs/initializes/shuts down a short-lived NativeOSEngine and returns live list_voices(); NativeOSEngine deliberately has NO static VOICES attribute (asserted by test) so the static-vs-dynamic break is structural. native_os registered across all 5 registry seams; list_engines() = [native_os, kokoro, piper] (native_os first, the default).
- [Phase ?]: [Phase 03 plan 03]: default TTS engine flipped kokoro->native_os and voice af_heart->'' (D-01); NO migration (clean-break) — existing config.yaml untouched, only fresh configs change. The two documented known-break tests (test_tts_registry ascii_only/list_engines + test_config defaults) fixed in the SAME wave; coverage preserved by splitting the flipped ascii-only assertion into native_os-registered + genuinely-unknown cases. Full suite 374 passed / 4 skipped (remaining skips = Plan 04 filter_voices/resolve_default_voice + Plan 05 WinRT/SAPI5 boundaries).
- [Phase 03]: [Phase 03 plan 04]: Voice-attribute picker UX (NATIVE-05) — pure Streamlit-free helpers filter_voices/order_by_quality/resolve_default_voice live in native_os_engine.py (no streamlit import; unit-tested), the UI wires them. Upload + Settings expose a language filter + quality/tier filter + name search around the voice dropdown (D-07), default to the OS system voice with best-quality-preferred ordering, system-language first (D-08/D-09). Per-engine remembered voice persists in app_settings under `tts.default_voice.<engine_name>` across engine-switch + restart and never preselects an absent id — resolve_default_voice validates the remembered id against the live list, else engine default (D-03 / Pitfall 5; T-03-11 mitigation). get_engine_voices wrapped in @st.cache_data keyed by engine name so `say -v '?'` is not re-shelled per keystroke (T-03-12). Dismissible native_os download hint via durable `tts.native_hint_dismissed` flag (D-10). Settings treats native_os as a no-model-file engine (skips kokoro/piper model-path validation).
- [Phase 03]: [Phase 03 plan 04, deviation #1 Rule-1 bug surfaced during human-verify]: An empty filter/search result crashed the picker with KeyError: None (selected voice id resolved to None, then voice_options[None] was indexed). Fixed with a None-safe resolve_selected_voice_id helper + a friendly "no voices match" empty-state message in both pickers + a regression test (commit 7be54ac). D-01 (fresh-config-only default flip, NO migration shim) and D-02 (picker shows only the selected engine's voices) were left UNTOUCHED — the human's "piper shown first" / "Amélie not on piper" reports were these decisions working as designed, not bugs. Full suite 377 passed / 2 skipped (remaining skips = Plan 05 WinRT/SAPI5 boundaries).
- [Phase 03]: [Phase 03 plan 05]: Windows WinRT branch of NativeOSEngine implemented (NATIVE-02). Four winrt-* packages (SpeechSynthesis/runtime/Storage.Streams/Foundation >=3.2.1) platform-gated to `; sys_platform == 'win32'` (pyproject) / `"win32"` (requirements), mirroring audioop-lts — the #1 macOS-install constraint HELD + verified (pip --dry-run ignores all four; engine imports with no winrt; no module-top winrt import). _winrt_synth uses bare `await synthesize_text_to_stream_async` (NEVER create_task — PyWinRT _async methods are awaitable but not coroutines) + `bytes(bytearray(buf))` buffer-protocol read (NEVER DataReader, maintainer guidance); _winrt_list_voices maps VoiceInformation→TTSVoice with tier from "OneCore" in id; _winrt_default_voice_id = get_default_voice().id (D-02). D-11 SAPI5-only = is_sapi5_only(voices) @staticmethod predicate (no voice id contains "OneCore") that also sets self._sapi5_only during enumeration. winrt imports lazy inside the win32 branch only. Branch logic mock-tested on macOS (patch.dict(sys.modules,{...}) with async fakes + a real bytearray Buffer so bytes(bytearray(buf)) is the proven path). Full suite 379 passed.
- [Phase 03]: [Phase 03 plan 05, user-approved deviation]: Task 3 (blocking Windows WinRT UAT) DEFERRED — no Windows box at execution time; user will run it after all other phases complete. Instead of pausing at the checkpoint, a self-contained 03-05-WINDOWS-UAT-DEFERRED.md was written (7-step Windows verification, A1 pinning via dir(SpeechSynthesizer), neural synth + SAPI5 note + zero-download audio + OS default voice, the Task 3 acceptance criteria, the 03-VALIDATION manual-only rows, requirements/decisions, closeout). Assumption A1 (exact PyWinRT snake_case spelling — get_all_voices/get_default_voice/voice setter) remains the single most likely Windows-side fix point. NATIVE-02/03/04/05 Windows surface stays PENDING until that UAT runs; ROADMAP/REQUIREMENTS deliberately NOT modified by this plan.
- [Phase 04 plan 02]: Generic download substrate (diana/downloads/downloader.py) is import-clean of piper/kokoro/streamlit (D-19) — download_file copies RESEARCH Pattern 1 verbatim (Range -> .part: 206 appends / 200 resets; total from manifest size_bytes/Content-Range, never a zero Content-Length; iter_content 64KB; md5-verify-then-atomic-os.replace, delete-.part-on-mismatch; cancel leaves .part for resume), has_space ancestor-walks a not-yet-created model_dir (D-05), clean_partials(directory=None) defaults to model_dir() for the zero-arg D-18 bulk action.
- [Phase 04 plan 02]: Piper catalog (diana/tts/catalog.py) = pure parse_manifest + thin load_bundled_manifest (offline, D-02) / refresh_catalog (only network touch; degrades to bundled on failure). Bundled piper_voices_curated.json = 9 best-per-language voices fetched VERBATIM from live manifest (verified size_bytes+md5; upstream commit pinned, Pitfall 6) — no invented digests. install_state cheap filesystem probes (ENGINE-01). download_url named per the binding scaffold (not plan's download_url_for); piper_footprint_bytes=0 when absent. package-data for data/*.json+samples (Phase-6 must verify PyInstaller); addopts '-m not network' excludes the opt-in net smoke.
- [Phase 04 plan 03]: WALKING SLICE (D-19) — Settings restructured into st.tabs (General/Voices/Processing/LLM Cleaning/News) with a dedicated Voices management hub (D-09); existing sections moved in unchanged, one Save button kept, tab-switching stays cheap. Only the single-Piper-voice Install path is fully live this plan (full browse/filter/group-by-language deferred to 04-04). The slice runs the Plan-02 substrate end-to-end through the real UI against the real network: footprint/install-state badge (Ready vs "~X MB, downloads on first use", ENGINE-03/D-11) → has_space disk pre-check that refuses before any bytes (D-05, T-04-DISK) → UI-spawned daemon threading.Thread calling download_file for the .onnx + .onnx.json (RESEARCH Pattern 3, NO in-repo precedent) writing only to st.session_state.dl_state → @st.fragment(run_every=0.5s) byte-progress poller (the thread is st.*-free; worker.py/pipeline.py untouched, ENGINE-04/T-04-SRC) → md5 atomic install → selectable for a job (VOICE-02/05). Re-trigger guarded on in-flight dl_state + serialized to one in-flight download (Pitfall 3, T-04-RETRIG). Human-verify checkpoint APPROVED; suite 391→428 passed.
- [Phase 04 plan 03, deviation #1 Rule-1 bug surfaced during human-verify]: Resume never appeared after Cancel because cancellation was not a terminal state (only in-flight vs done/error), so an interrupted install could not be resumed (defeating D-06). Fixed by adding a `cancelled` terminal marker + pure _download_action/_can_spawn_download helpers (unit-tested) so the flow is Cancel→"Cancelling…"→Resume and Resume offsets from the existing .part rather than restarting at 0 (D-06/D-07). Commit 02f2eca; new tests/test_settings_downloads.py.
- [Phase 04 plan 03, deviation #2 Rule-1 bug surfaced during human-verify]: Installed Piper voices did not appear in the Upload/Settings pickers (VOICE-05 unmet in practice) because get_engine_voices("piper") returned only static PiperEngine.VOICES. Fixed by adding install_state.list_installed_piper_voice_ids() (cheap model-dir glob) + a DYNAMIC piper branch in registry.get_engine_voices that MERGES static + installed ids (deduped, Kokoro files excluded), labeled via catalog.voice_label_for_id — cheap filesystem probe, NO heavy onnxruntime/piper import (ENGINE-01). This is the shared enumeration foundation 04-05's all_engine_voices builds on (built once here so 04-05 does not duplicate it). Commit 55e87f9; new tests/test_piper_enumeration.py.
- [Phase 04 plan 03, deviation #3 Rule-1 bug surfaced during human-verify]: (A) Even after deviation #2, a freshly installed voice required an app restart to appear because the per-page @st.cache_data _cached_voices served a stale list; (B) installed-voice display names did not match static PiperEngine.VOICES formatting. Fixed by (A) unifying the per-page caches into a shared diana/dashboard/voice_cache.py and calling clear_voice_cache() from the SCRIPT thread on the install-done transition (no restart; worker thread stays st.*-free), and (B) pure _format_piper_name/_parse_piper_id in catalog.py so installed names format uniformly as "Lessac (US Medium)". Commit 9c36960; new tests/test_voice_cache.py + extended test_piper_enumeration.py. (Effective files_modified for 04-03 = 5_Settings.py + 1_Upload.py + voice_cache.py[new] + registry.py + install_state.py + catalog.py + 3 new test files — the plan frontmatter had named only 5_Settings.py.) Full "Show all" catalog browse/preview/import is Wave 4 (04-04); cross-engine browser + editable labels + Upload-dropdown badges is Wave 5 (04-05).

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- Phases 3, 5, and 6 flagged MEDIUM-confidence in research — plan each with `/gsd:plan-phase --research-phase` (Windows WinRT TTS; heavy-engine APIs; packaging/signing hooks).
- Pre-existing News `unsafe_allow_html=True` XSS surface (`3_News.py:237`) is tracked for Phase 7 (HARD-03) — Phase 1 plans must not introduce or worsen it.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Windows UAT (blocking) | Phase 03 plan 05 Task 3 — Windows WinRT UAT: pin PyWinRT spelling (A1) + confirm neural synth, picker enumeration, OS default voice, and SAPI5-only D-11 note with zero-download audio on a real Windows 10/11 box. Closes the Windows surface of NATIVE-02/03/04/05. Self-contained checklist: `.planning/phases/03-native-os-tts-new-default/03-05-WINDOWS-UAT-DEFERRED.md` | Pending (user runs after all other phases) | 2026-06-15 (Phase 03) |

## Session Continuity

Last session: 2026-06-15T15:00:41.000Z
Stopped at: Completed Phase 04 Plan 03 (walking slice — tabbed Settings + Voices hub + one-Piper-voice threaded install proven end-to-end through the UI; human-verify APPROVED; 3 in-plan deviations). Next: 04-04 (full catalog browse + preview + manual import), Wave 4.
Resume file: None
