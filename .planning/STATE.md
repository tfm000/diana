---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: verifying
stopped_at: Completed 02-04-PLAN.md (figures/captions/footnotes + corpus completion — CLEAN-01/03/08)
last_updated: "2026-06-01T00:31:03.547Z"
last_activity: 2026-06-01
progress:
  total_phases: 7
  completed_phases: 2
  total_plans: 8
  completed_plans: 8
  percent: 29
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-29)

**Core value:** Convert documents into listenable audiobooks entirely on-device — so even private or sensitive files can be turned into audio without sending them anywhere.
**Current focus:** Phase 02 — rule-based-cleaner-overhaul

## Current Position

Phase: 02 (rule-based-cleaner-overhaul) — EXECUTING
Plan: 4 of 4
Status: Phase complete — ready for verification
Last activity: 2026-06-01

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 8
- Average duration: ~4 min implementation (plus blocking human-verify checkpoint gaps)
- Total execution time: ~0.3 hours active

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 01 | 4/4 | ~57min wall impl (incl. deviation tweaks; excludes checkpoint gaps) | ~4min impl |
| 01 | 4 | - | - |

**Recent Trend:**

- Last 5 plans: 01-01 (3min), 01-02 (~24min wall incl. checkpoint gap), 01-03 (~3min impl + ~5min next-day deviation tweaks; wall ~26h spanning blocking human-verify), 01-04 (~5min impl across RED/GREEN/wiring + ~1min related 01-01 follow-up surfaced during verify; wall ~14h spanning blocking human-verify)
- Trend: implementation velocity stable; 01-04 had zero in-plan deviations (matches 01-01); the only follow-up commit (b8e70d0) was attributed back to 01-01 not 01-04. Across Phase 01: deviation rate landed at 2 expansions in 01-03 + 1 amended decision in 01-02 + 0 in 01-01/01-04, all surfacing during human-verify.

*Updated after each plan completion*
| Phase 01 P02 | ~24min | 3 tasks | 8 files |
| Phase 01 P03 | ~3min impl (wall ~26h spanning checkpoint) | 4 tasks (3 auto + 1 blocking checkpoint) | 7 files (6 planned + 1 scope-expansion via deviation #1) |
| Phase 01 P04 | ~5min impl (wall ~14h spanning checkpoint) | 3 tasks (2 auto + 1 blocking checkpoint) | 3 files (matches plan files_modified exactly; +1 unrelated Kokoro-paths fix attributed to 01-01, not counted here) |
| Phase 02 P01 | 9min | 3 tasks | 19 files |
| Phase 02 P02 | 4min | 2 tasks | 13 files |
| Phase 02 P03 | 5min | 2 tasks | 7 files |
| Phase 02 P04 | 13min | 3 tasks | 9 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

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
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-01T00:31:03.542Z
Stopped at: Completed 02-04-PLAN.md (figures/captions/footnotes + corpus completion — CLEAN-01/03/08)
Resume file: None
