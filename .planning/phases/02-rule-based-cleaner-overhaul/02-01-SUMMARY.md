---
phase: 02-rule-based-cleaner-overhaul
plan: 01
subsystem: testing
tags: [cleaner, tts, unicodedata, transliteration, regex, pytest, golden-corpus, format-aware]

# Dependency graph
requires:
  - phase: 01-foundation-privacy-toggle
    provides: "rule-based clean_text as the DEFAULT LLM-off cleaning path (D-06); the pipeline clean/LLM branch gating clean_text vs llm_clean_text"
provides:
  - "Format-aware + engine-aware clean_text(text, *, source_format=None, ascii_only=False) keyword-only signature (clean break, no shim)"
  - "engine_is_ascii_only(name) static registry capability map (kokoro True, piper False, unknown True), no heavy import"
  - "Three narrowed over-strippers: conservative table-block, label-discriminated chart-fragment, blank-line-boundary page-number — years/headings/lone-numeric-sentences survive"
  - "Format-aware header/footer half of CLEAN-02 (reused _remove_common_footers + _remove_repeated_lines + boundary page-number rule)"
  - "Engine-conditional transliteration (_transliterate_ascii + _TRANSLIT_SUPP): café->cafe for ASCII engines, café preserved for UTF-8, never caf"
  - "tests/test_cleaner_corpus.py two-layer golden-corpus harness with an INCREMENTALLY-assembled invariant set + the 'Wave N adds' extension contract"
  - "tests/fixtures/cleaner/ synthetic snapshot pairs (years/headings/page-number/footer/table)"
  - "02-VALIDATION.md Wave-0 gate flipped (wave_0_complete + nyquist_compliant true) for the whole phase"
affects: [02-02, 02-03, 02-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Keyword-only signature widening as a clean break (defaults preserve current behaviour; no dual-branch shim)"
    - "Engine character-capability as a static name->bool registry map queried with no heavy import"
    - "Engine concerns (ascii_only) resolved at the call site, never inside cleaner.py (keeps it diana.tts-free, pure-stdlib)"
    - "NFKD + supplemental-map transliteration via a per-char unicodedata loop (no regex, no ReDoS surface)"
    - "Two-layer golden corpus (property invariants + snapshot fixtures) with invariants assembled incrementally across waves"

key-files:
  created:
    - "tests/test_cleaner_corpus.py"
    - "tests/fixtures/cleaner/ (5 .in.txt/.expected.txt pairs)"
    - ".planning/phases/02-rule-based-cleaner-overhaul/deferred-items.md"
  modified:
    - "diana/processing/cleaner.py"
    - "diana/tts/registry.py"
    - "diana/processing/pipeline.py"
    - "diana/processing/llm_cleaner.py"
    - "diana/news/summarizer.py"
    - "tests/test_cleaner.py"
    - "tests/test_tts_registry.py"
    - ".planning/phases/02-rule-based-cleaner-overhaul/02-VALIDATION.md"

key-decisions:
  - "clean_text default ascii_only=False (non-destructive; every production call site passes an explicit engine-derived value)"
  - "ascii_only resolved in pipeline.py via engine_is_ascii_only(job.tts_engine), passed in — cleaner.py stays free of any diana.tts import"
  - "build_digest_text cleans with ascii_only=False (UTF-8 preserved); the resulting txt Job is re-cleaned by the pipeline with the real engine's ASCII net (intentional double-clean)"
  - "Chart-fragment removal requires the >=3 noise cluster to contain at least one short LABEL (refinement beyond RESEARCH's pure numeric-fraction predicate) so label-less year/number lists are preserved"
  - "Wave-1 corpus invariants assert only preservation + basic structural; URL/email (02-03) and figure/footnote (02-04) removal invariants are deferred to a documented 'Wave N adds' extension point"

patterns-established:
  - "Static name->bool capability map in the TTS registry no-import tier (mirrors list_engines)"
  - "Incrementally-assembled corpus invariant set: each later slice appends its removal invariant as it lands the stage"

requirements-completed: [CLEAN-02, CLEAN-04, CLEAN-07, CLEAN-08]

# Metrics
duration: 9min
completed: 2026-05-31
---

# Phase 2 Plan 01: Cleaner Format/Engine Seam + Stop Over-Stripping + Golden Corpus Summary

**Widened clean_text to a keyword-only (text, *, source_format, ascii_only) signature, added a no-heavy-import engine_is_ascii_only registry map, narrowed the three over-strippers so years/headings/lone-numeric-sentences survive, made transliteration engine-conditional (café->cafe never caf), and stood up the two-layer golden-corpus harness that flips the phase Wave-0 gate.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-05-31T23:39:46Z
- **Completed:** 2026-05-31T23:49:xxZ
- **Tasks:** 3 (all `type="auto" tdd="true"`)
- **Files modified/created:** 19 (committed)

## Accomplishments

- **Architecture seam (CLEAN-02 param + Decision 5):** `clean_text(text, *, source_format=None, ascii_only=False)` — keyword-only, clean break, every existing positional `clean_text(str)` still runs. `engine_is_ascii_only(name)` static map in `diana/tts/registry.py` resolves `kokoro->True, piper->False, unknown->True` with no engine import. All 3 call sites wired: `pipeline.py` resolves `ascii_only = engine_is_ascii_only(job.tts_engine)` and passes `source_format=job.file_type`; `llm_cleaner.py` threads both through `llm_clean_text`/`_clean_chunk_with_fallback` and gates the trailing net (`strip_non_speakable(combined) if ascii_only else combined`); `summarizer.py` `build_digest_text` cleans with `source_format="web", ascii_only=False`.
- **Stopped destroying content (CLEAN-04 + CLEAN-07 over-stripping):** the three over-strippers are narrowed conservatively. Years (`2019/2020/2021`), heading stacks (`Introduction/Methods/Results`), and lone numeric sentences (`In 2019, 2020 and 2021 sales rose`) now survive; true page numbers and >=2-row tables are still removed.
- **Format-aware header/footer half of CLEAN-02:** reused `_remove_common_footers` (copyright/DOI/arXiv/journal/`Page X of Y`) + `_remove_repeated_lines` (running headers) **unchanged**, plus the new blank-line-boundary page-number rule — a PDF `Page 3 of 10`/copyright/DOI footer strips while TXT prose carrying similar tokens (`We covered pages 3 through 10 of the manual.`) is kept. Pinned by `TestHeadersFooters`. No parser change.
- **Engine-conditional non-ASCII (CLEAN-07):** `_transliterate_ascii` (NFKD + `_TRANSLIT_SUPP`) folds `café->cafe`, `Straße->Strasse`, `naïve->naive`, `Zürich->Zurich` for ASCII engines, preserves `café` for UTF-8 engines, and never yields the bare stem `caf`. Pure per-char `unicodedata` loop — no regex.
- **Golden corpus (CLEAN-08 foundation):** `tests/test_cleaner_corpus.py` two-layer suite (invariants + snapshot loader) + `tests/fixtures/cleaner/` snapshot pairs. The planted-regression loud-failure check passes (legible diff). `02-VALIDATION.md` Wave-0 gate flipped to `true`.

## Task Commits

Each task committed atomically (TDD: RED check run before each GREEN implementation):

1. **Task 1: Widen signature + engine_is_ascii_only + wire call sites** - `3f7475f` (feat)
2. **Task 2: Narrow the three over-strippers + format-aware footers** - `e6b1f0e` (fix)
3. **Task 3: Engine-conditional transliteration + corpus harness + flip VALIDATION** - `fead76e` (feat)

**Plan metadata:** (final docs commit — STATE/ROADMAP/REQUIREMENTS/SUMMARY)

## Key Artifacts (per plan `<output>` spec)

### Final `clean_text` signature
```python
def clean_text(text: str, *, source_format: str | None = None, ascii_only: bool = False) -> str:
```
Stage body change in this plan: `_remove_page_numbers(text, source_format)`; `_transliterate_ascii` then `strip_non_speakable` both gated behind `if ascii_only:`; `_collapse_whitespace` stays last. Existing stage order otherwise preserved.

### `_ASCII_ONLY_ENGINES` map
```python
_ASCII_ONLY_ENGINES = {"kokoro": True, "piper": False}   # unknown -> True; native_os (Phase 3) -> False
```

### Wired call sites
- `pipeline.py` — `ascii_only = engine_is_ascii_only(job.tts_engine)`; `clean_text(text, source_format=job.file_type, ascii_only=ascii_only)` / `llm_clean_text(text, llm_cfg, source_format=job.file_type, ascii_only=ascii_only)`.
- `llm_cleaner.py` — both fallback `clean_text(chunk, source_format=source_format, ascii_only=ascii_only)`; trailing `return strip_non_speakable(combined) if ascii_only else combined`.
- `summarizer.py` — `build_digest_text` → `clean_text(raw, source_format="web", ascii_only=False)`.
- **Summarizer no-regression proof:** `tests/test_news_digest.py::TestCleanerApplied::test_strips_urls_via_clean_text` is green — it proves the wired summarizer call still runs `clean_text` (URL stripped, prose kept) under the new kwargs (a no-regression check, not a kwargs-passed assertion).

### The three narrowed over-strippers (before -> after)
- **Tables (`_remove_tables`, CLEAN-04):** numeric branch now requires `>=2` adjacent structured rows (`_is_structured_row`). `In 2019, 2020 and 2021 sales rose sharply.` BEFORE: line risked numeric strip → now KEPT. A 2-row numeric block (`12.5 34.2 56.1` / `11.3 22.4 33.5`) still removed. Pipe/tab tables still removed.
- **Chart fragments (`_remove_chart_fragments`, CLEAN-07):** drops a `>=3` noise cluster only when it contains a short LABEL (`_is_chart_label`). `Introduction/Methods/Results` BEFORE: deleted as a short-line cluster → now KEPT (`_SECTION_WORDS` allow-list + label requirement). `2019/2020/2021` (label-less numeric run) KEPT. `X axis / Y axis / 0 / 10 / 20` (labels + ticks) still removed.
- **Page numbers (`_remove_page_numbers`, CLEAN-02):** strips a 1-4 digit line only when blank-flanked. `Some text.\n42\nMore text.` BEFORE: `42` removed → now KEPT (not a boundary). `End of section.\n\n42\n\nNew section.` → `42` removed (isolated paragraph = page number). `There are 42 items.` KEPT. `source_format` threaded (reserved for a future `\f` sentinel; parsers untouched).

### Transliteration map
```python
_TRANSLIT_SUPP = {"ß":"ss","æ":"ae","Æ":"AE","œ":"oe","Œ":"OE","ø":"o","Ø":"O",
                  "đ":"d","Đ":"D","ł":"l","Ł":"L","ð":"d","Ð":"D","þ":"th","Þ":"Th"}
```
Combining-diacritic letters (é, ï, ü, ç …) are handled by NFKD and deliberately NOT in the map.

### Wave-1 corpus invariant subset + "Wave N adds" contract
`_invariants(out, *, ascii_only=False)` asserts ONLY, at Wave 1:
- **Structural (live):** no pipe-table row `^\|.*\|$`; no ` ,`; no `( )`; no double space; no `\n\n\n`.
- **Engine-conditional:** when `ascii_only`, `all(ord(c) < 128 …)`.
Preservation invariants (headings/years/accents) are asserted per-fixture in the snapshot + `TestPreservationInvariants` classes.
**It does NOT yet assert** no-URL / no-`www.` / no-email (added by **02-03**) or no-`(Figure|Table|Fig.|Tab.)\d` figure-reference token / no-LaTeX-brace residue (added by **02-04**) — adding them now would fail Wave-1 fixtures that may still carry those tokens. The `_invariants` docstring carries a clearly-marked "Wave N adds (extension point …)" block so 02-03/02-04 append their removal invariant AS they land the stage. Snapshot tests/classes use the `-k` selectors `preserve`, `tables`, `headers_footers` from VALIDATION.

### 02-VALIDATION.md frontmatter flip
`wave_0_complete: false -> true`, `nyquist_compliant: false -> true` (the Wave-0 corpus harness + fixtures now exist; every task's automated verify binds to a VALIDATION selector/behavior).

### Observed loud-failure diff (planted-regression check, CLEAN-08 / ROADMAP criterion #4)
`_remove_page_numbers` was reverted to the old `re.sub(r"(?m)^\s*\d{1,4}\s*$", "", text)` **via runtime monkeypatch (source file never edited)** and the `years_preserve` snapshot went RED:
```
--- expected
+++ actual(regressed)
@@ -1,7 +1,3 @@
 Annual sales figures by year:
 
-2019
-2020
-2021
-
 Growth continued each year.
```
Restored immediately; corpus suite green (14 passed). Confirmed the boundary-aware body is intact in source.

## Files Created/Modified
- `diana/processing/cleaner.py` - widened signature; `_SECTION_WORDS` + `_TRANSLIT_SUPP` maps; rewritten `_remove_tables` (+`_is_structured_row`), `_remove_chart_fragments` (+`_is_numeric_line`/`_is_chart_label`/`_is_noise_line`), `_remove_page_numbers` (boundary-aware); new `_transliterate_ascii`; `ascii_only`-gated net.
- `diana/tts/registry.py` - `_ASCII_ONLY_ENGINES` map + `engine_is_ascii_only()` (no heavy import).
- `diana/processing/pipeline.py` - import `engine_is_ascii_only`; resolve `ascii_only`; pass `source_format`/`ascii_only` to both branches.
- `diana/processing/llm_cleaner.py` - thread `source_format`/`ascii_only` through `llm_clean_text`/`_clean_chunk_with_fallback`; gate the trailing net.
- `diana/news/summarizer.py` - `build_digest_text` cleans with `source_format="web", ascii_only=False`.
- `tests/test_tts_registry.py` - `TestEngineIsAsciiOnly` (RED-first).
- `tests/test_cleaner.py` - flipped Regression #1 (`test_accented_chars` parametrized) + #2 (boundary page number); added `TestHeadersFooters`, `TestChartFragments::test_section_headings_preserved`, transliteration-not-truncation, UTF-8-preserved net case; the two un-flagged net tests (math/emoji) now assert via `ascii_only=True`.
- `tests/test_cleaner_corpus.py` - NEW two-layer golden-corpus suite.
- `tests/fixtures/cleaner/*.in.txt` / `*.expected.txt` - NEW snapshot pairs.
- `.planning/phases/02-rule-based-cleaner-overhaul/02-VALIDATION.md` - Wave-0 gate flip.

## Decisions Made
- See `key-decisions` frontmatter. Most consequential: the chart-fragment **label requirement** — RESEARCH Q2's `_is_noise_line` (numeric-fraction >=0.6) alone would have deleted a year list (`2019/2020/2021`), which the CLEAN-07 acceptance one-liner explicitly forbids. Refined the heuristic so a `>=3` noise cluster is removed only when it contains a short non-numeric label (chart = ticks beside labels); a label-less numeric run is preserved and left to the table/page-number stages. This keeps both `test_short_cluster_removed` (X axis/Y axis/0/10/20 removed) and the year-list preservation green.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Two un-flagged ASCII-net tests encoded the now-conditional net**
- **Found during:** Task 1 (signature widening — gating `strip_non_speakable` behind `ascii_only`).
- **Issue:** `TestStripNonSpeakable::test_math_symbols_removed` and `test_emoji_removed` called bare `clean_text(str)` and asserted the net's removal of `≤`/emoji. With the net now engine-conditional (`ascii_only=False` default skips it), they failed. The plan named only Regression #1 (`test_accented_chars_removed`) as a guaranteed flip; these two are the same class of stale "net is unconditional" assertion.
- **Fix:** Updated both to assert the net behaviour explicitly via `ascii_only=True`, and added `test_non_ascii_preserved_for_utf8_engine` to pin the new default-preserves-UTF-8 direction.
- **Files modified:** tests/test_cleaner.py
- **Verification:** `tests/test_cleaner.py::TestStripNonSpeakable` green (7 passed); full suite green.
- **Committed in:** 3f7475f (Task 1 commit)

**2. [Rule 2 - Missing critical] Chart-fragment label discrimination to satisfy year-preservation**
- **Found during:** Task 2 (narrowing `_remove_chart_fragments`).
- **Issue:** The RESEARCH-verified `_is_noise_line` (pure numeric-fraction predicate) flags standalone years as noise; a 3-line year list (`2019/2020/2021`) ran ahead of `_remove_page_numbers` and was deleted as a chart cluster — over-stripping that the CLEAN-07 `years-kept` acceptance one-liner forbids.
- **Fix:** Split the predicate into `_is_numeric_line` + `_is_chart_label` and required a `>=3` cluster to contain at least one label before deletion (a chart has ticks beside labels; a year/number column has none).
- **Files modified:** diana/processing/cleaner.py
- **Verification:** `years-kept` + `chart-cluster-removed` one-liners both pass; `TestChartFragments`/`TestTableRemoval` green.
- **Committed in:** e6b1f0e (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug, 1 Rule 2 missing-critical). Both stay within the conservative-bias mandate (preserve more, not less) and the plan's explicit acceptance criteria. No scope creep; no parser change; no new dependency.
**Impact on plan:** Necessary to satisfy the plan's own acceptance one-liners (years-kept) and keep the full suite green under the new engine-conditional net.

## Issues Encountered
- **Pre-existing, out-of-scope test failure:** `tests/test_llm_client_anthropic_cli.py::test_anthropic_cli_real_call` fails (real end-to-end CLI call needing an active `claude login` session + Node.js; not skipped because the SDK is installed but the live session is unavailable). Verified it fails identically on the clean baseline (commit 09c1a89) and touches no plan file. Logged to `deferred-items.md`; NOT fixed (SCOPE BOUNDARY).

## Known Stubs
None. No hardcoded empties, placeholders, or `NotImplementedError` introduced; the cleaner stays pure-stdlib and deterministic.

## User Setup Required
None - no external service configuration required. The cleaner remains pure-stdlib (`re`/`unicodedata`/`collections`); no new dependency added.

## Next Phase Readiness
- The format/engine seam, the narrowed over-strippers, and the corpus harness are the foundation 02-02/02-03/02-04 build on — they all edit `cleaner.py` and rely on `ascii_only`/`source_format` and the invariant harness being present.
- **Contract for later plans:** append removal invariants at the `_invariants` "Wave N adds" extension point AS each stage lands (02-03 URL/email; 02-04 figure/footnote/LaTeX). Hard stage-ordering constraints for the remaining slices are documented in 02-RESEARCH § Stage Ordering (currency-before-inline-math is load-bearing).
- No blockers introduced.

## Self-Check: PASSED

- Created files verified on disk: `tests/test_cleaner_corpus.py`, all 5 fixture pairs under `tests/fixtures/cleaner/`, `02-01-SUMMARY.md`, `deferred-items.md` — all FOUND.
- Task commits verified in git log: `3f7475f`, `e6b1f0e`, `fead76e` — all FOUND.
- Full project suite: 267 passed (only the pre-existing, out-of-scope `test_anthropic_cli_real_call` fails; logged in deferred-items.md).

---
*Phase: 02-rule-based-cleaner-overhaul*
*Completed: 2026-05-31*
