---
phase: 02-rule-based-cleaner-overhaul
plan: 04
subsystem: processing
tags: [cleaner, tts, figures, captions, footnotes, regex, redos, pytest, golden-corpus, stage-ordering]

# Dependency graph
requires:
  - phase: 02-rule-based-cleaner-overhaul
    plan: 01
    provides: "clean_text(text, *, source_format, ascii_only) seam; line-oriented split/keep/join idiom; the two-layer golden-corpus harness (_invariants + snapshot loader) with the 'Wave N adds' extension contract; the narrowed _remove_page_numbers (used as the planted-regression target)"
  - phase: 02-rule-based-cleaner-overhaul
    plan: 02
    provides: "_normalize_currency_percent before _remove_inline_math ordering; the abbreviation expansion the stage-order test pins"
  - phase: 02-rule-based-cleaner-overhaul
    plan: 03
    provides: "_remove_code_blocks / _strip_list_markers / _strip_urls / _strip_emails stages and their corpus fixtures; the no-URL/no-email removal invariant already registered (this plan registers the final no-figure-token invariant beside it)"
provides:
  - "_handle_captions_and_refs: replaces the blunt _remove_figure_table_refs. CAPTION branch (label at a segment start + ':'/'.' + capitalized prose) strips the label+delimiter and KEEPS the sentence; REFERENCE branch removes the inline token (whole cross-reference parentheticals first, then bare tokens) then _repair_dangling fixes the grammar."
  - "_repair_dangling: empty-parens / 'in ,'->'in' / ' ,'->',' with BOUNDED ({0,8}/{1,8}) horizontal-whitespace runs (ReDoS-safe; the unbounded form was O(n^2) under re.sub and is now capped). Drops the redundant double-space collapse (the final _collapse_whitespace heals it)."
  - "Residual EPUB/MD image-artifact strip (_IMAGE_ARTIFACT_RE): a bounded <stem><digits>.<ext> filename token (imageN.png, diagram2.jpg). Literal MD image syntax never reaches the cleaner (parser-stripped) so this is residual-token-only; md_parser stays read-only."
  - "Superscript-digit footnote-marker removal (_SUPERSCRIPT_MARKER_RE, U+00B9/B2/B3 + U+2070-2079) inside _remove_citations — for ALL engines, not just the Kokoro ASCII net. Bounded {1,4}, fixed codepoint class."
  - "_remove_footnote_bodies: best-effort drop of a conservative marker-prefixed ([n] or n.) capitalized 20+-char block after a blank line, all-lines-match; the 20+-char gate keeps a short numbered LIST from being eaten. Wired at stage 6 (after citations, before captions/refs)."
  - "no-figure/table-reference-token removal invariant registered into tests/test_cleaner_corpus.py _invariants — completing the removal-invariant set; holds across all 15 snapshots."
  - "Complete-stage-ordering test (TestStageOrdering::test_orchestrator_stage_order) pinning every hard ordering constraint via inspect.getsource(clean_text).index()."
  - "figures + footnotes + figures_epub corpus fixtures + TestSnapshotsFigures/TestSnapshotsFootnotes so -k figures / -k footnotes resolve; the corpus now spans PDF/EPUB/TXT flavors and both ascii_only axes."
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Caption vs reference is discriminated by POSITION: a label anchored at a segment boundary (line start or just after a sentence terminator) followed by ':'/'.' and a capitalized word is a caption (keep prose); a label embedded mid-sentence is a reference (remove + repair)."
    - "Whole cross-reference parentheticals ('(see Figure 2)') are removed as a unit BEFORE bare-token removal, so no '(see )' residue is left for the dangling repair."
    - "Bounded whitespace quantifiers are the ReDoS mitigation for re.sub scanning: '[^\\S\\n]{1,8}' (capped), never '[^\\S\\n]+' followed by a maybe-absent literal — the unbounded form is O(n^2) on a long adversarial space run (caught at runtime this plan)."
    - "Footnote-body detection is honestly best-effort (no page model post-extraction): markers always; bodies only on a conservative 20+-char marker-prefixed capitalized block after a blank line, all-lines-match. The 'n.' body form survives the citation strip and stays detectable at stage 6."
    - "Superscript footnote markers must be removed explicitly for ALL engines — they are not in the smart-quote/dash _normalize_unicode replacements, so a UTF-8 engine would otherwise keep them."
    - "Incremental corpus contract closed: this wave registers the final no-figure-token removal invariant, completing the full removal set (pipe-table + no-URL/email + no-figure-token + no-dangling) across every snapshot."

key-files:
  created:
    - "tests/fixtures/cleaner/figures.in.txt / .expected.txt"
    - "tests/fixtures/cleaner/footnotes.in.txt / .expected.txt"
    - "tests/fixtures/cleaner/figures_epub.in.txt / .expected.txt"
  modified:
    - "diana/processing/cleaner.py"
    - "tests/test_cleaner.py"
    - "tests/test_cleaner_corpus.py"

key-decisions:
  - "Followed the RESEARCH _repair_dangling substitution table as the authoritative contract ('in ,'->'in'), so 'As shown in Figure 3, the trend is up.' -> 'As shown in the trend is up.' The plan's prose example ('As shown the trend') was illustrative; the figures fixture encodes the RESEARCH-spec result and the plan's acceptance one-liner accepts it."
  - "DROPPED two patterns from my first _repair_dangling draft because they caused O(n^2) catastrophic backtracking under re.sub on adversarial space runs (36s / 9s observed): the non-spec ' .'->'.' substitution (removed entirely — outside the RESEARCH 4-substitution spec, and _collapse_whitespace heals dangling stops) and the unbounded '[^\\S\\n]+,' form (re-bounded to '[^\\S\\n]{1,8},'). The redundant double-space collapse was also dropped (the final _collapse_whitespace pass owns it). Re-verified linear (worst 0.03s on 780k chars). This is a Rule-1 auto-fix of a ReDoS bug I introduced mid-task."
  - "Chose the 'n.' numbered form (not '[n]') for the footnote-body fixture because _remove_footnote_bodies runs AFTER _remove_citations (the firm stage-6 ordering), which strips '[n]' brackets first; the 'n.' form survives the citation strip and stays detectable, honoring both the ordering constraint and honest best-effort scope. The 20+-char gate is the disambiguator vs a short numbered list."
  - "Added an EPUB/UTF-8 figures fixture (figures_epub, ascii_only=False) in the Task-3 sweep so the corpus spans all three PDF/EPUB/TXT flavors (CLEAN-08 'spanning the flavors named in VALIDATION') and exercises the EPUB image-artifact path on the UTF-8-capable side. This is coverage-only — no production change."
  - "Kept the old _remove_figure_table_refs name only as documentary comments (never a call); the function definition is fully removed and the orchestrator calls _handle_captions_and_refs."

patterns-established:
  - "Every new pattern over untrusted document text is bounded/anchored with a capped quantifier — and verified linear at runtime against an adversarial input, not just inspected. The ReDoS axis (T-02-01) is the cleaner's only security surface and is now runtime-proven for the figure/caption/footnote stages too."
  - "Removal stages substitute the empty string (no placeholder/marker token)."

requirements-completed: [CLEAN-01, CLEAN-03, CLEAN-08]

# Metrics
duration: 13min
completed: 2026-06-01
---

# Phase 2 Plan 04: Figures / Captions / Footnotes + Corpus Completion Summary

**Closed the fuzziest cleaner slice (CLEAN-01/03) and completed the golden corpus (CLEAN-08): captions now KEEP their prose (only the label+colon are dropped) while inline figure/table references are removed and the dangling grammar repaired (no `in ,` / `( )` / double space); residual EPUB/MD image-filename tokens are stripped (literal MD image syntax never reaches the cleaner, so md_parser stays read-only); superscript footnote markers are removed for ALL engines and a conservative best-effort footnote-body block is dropped WITHOUT eating numbered lists; the complete 20-stage ordering is pinned by a source-index test; the final no-figure-token removal invariant is registered (completing the removal set across all 15 snapshots); and the planted-regression loud-failure check turned the corpus RED with a legible diff and was restored to green — demonstrating ROADMAP criterion #4.**

## Performance

- **Duration:** ~13 min
- **Started:** 2026-06-01T00:14:11Z
- **Tasks:** 3 (Task 1 & 2 `type="auto" tdd="true"`; Task 3 `type="auto"` integration/coverage sweep — no production behavior, so no RED→GREEN)
- **Files modified:** 3 (`cleaner.py`, `test_cleaner.py`, `test_cleaner_corpus.py`) + 6 fixture files created (all committed)

## Accomplishments

- **Caption-vs-reference handler (CLEAN-01), replacing the blunt remover:** `_handle_captions_and_refs` discriminates by POSITION. A label anchored at a segment boundary (`(?:(?<=^)|(?<=[.!?]\s))Figure|Table … \d{1,4}\s*[:.]\s+(?=[A-Z])`) followed by capitalized prose is a **caption** — the label+delimiter is stripped and the sentence kept (`"Figure 3: The system has three stages." → "The system has three stages."`). A label embedded mid-sentence is a **reference** — the whole cross-reference parenthetical (`(see Figure 2)`) is removed first (so no `(see )` residue), then bare tokens, then `_repair_dangling`. The old `_remove_figure_table_refs` (which left `: The system…` / `As shown in , the…`) is fully removed.
- **Dangling repair, made ReDoS-safe:** `_repair_dangling` applies the RESEARCH substitutions — empty parens `\([^\S\n]{0,8}\)`→"", `\bin[^\S\n]{1,8},`→"in", `[^\S\n]{1,8},`→",". The whitespace runs are **bounded** (the mitigation); my first draft used unbounded `[^\S\n]+` plus a non-spec `" ."→"."`, which backtracked catastrophically (36 s / 9 s on a 200k-space adversarial run) — caught and fixed mid-task (see Deviations).
- **Residual image-artifact strip (CLEAN-01), correctly scoped:** `_IMAGE_ARTIFACT_RE` removes a bounded `<stem><digits>.<ext>` filename token (`image1.png`, `diagram2.jpg`). A one-line comment records the parser-strips-syntax assumption; `git status diana/parsers/` is empty (md_parser untouched). Literal `![alt](img.png)` is dead against the real parser path and is deliberately NOT matched.
- **Superscript footnote markers for ALL engines (CLEAN-03):** `_SUPERSCRIPT_MARKER_RE` (`(?<=\w)[¹²³⁰-⁹]{1,4}`) removes U+00B9/B2/B3 + U+2070–U+2079 inside `_remove_citations` (stage 5). These are not in the `_normalize_unicode` replacements, so without this they survive for a UTF-8 engine (only Kokoro's ASCII net would catch them).
- **Best-effort footnote-body removal (CLEAN-03), protecting numbered lists:** `_remove_footnote_bodies` (stage 6, after citations, before captions) drops a contiguous block where every line matches `^\s*(?:\[\d+\]|\d+[.)])\s+[A-Z].{20,}$` AND has a preceding blank line. The 20+-char gate + all-lines-match rule keep a short numbered list (`1. First item to do`) intact — `TestCitations` and `TestListMarkerStrip` stayed green.
- **Complete stage-ordering pin (HIGH-5):** `TestStageOrdering::test_orchestrator_stage_order` asserts every hard constraint via `inspect.getsource(clean_text).index()`: currency<inline-math, citations<footnote-bodies<captions<code-blocks<table/chart, abbreviations<URL/email, chart-fragment<list-markers, and `_collapse_whitespace` last.
- **Corpus completion (CLEAN-08):** registered the final `no-figure-token` removal invariant (`not re.search(r"\b(Figure|Table|Fig\.|Tab\.)\s*\d", out)`) — completing the removal set. Added `figures`, `footnotes`, and an EPUB/UTF-8 `figures_epub` fixture so the corpus spans **PDF/EPUB/TXT** flavors and both `ascii_only` axes. Every VALIDATION `-k` selector resolves to ≥1 passing test; the complete `_invariants` sweep runs across all 15 snapshots.
- **ReDoS posture (T-02-01), runtime-proven:** after the mid-task fix, every new pattern runs linearly on adversarial input — worst `_handle_captions_and_refs` 0.03 s on 780k chars; superscript run 0.002 s; footnote-body bomb 0.026 s; full `clean_text` on a 660k-char reference bomb 0.17 s.

## Task Commits

Each task committed atomically (TDD: RED run and observed failing before each GREEN for Tasks 1–2):

1. **Task 1: Caption-vs-reference handler + dangling repair + residual image strip + figure-token invariant — CLEAN-01** — `1f9ea61` (feat)
2. **Task 2: Superscript footnote markers + best-effort footnote-body removal + complete-stage-ordering pin — CLEAN-03** — `5bc75fd` (feat)
3. **Task 3: Corpus completion sweep + EPUB flavor + planted-regression loud-failure verification — CLEAN-08** — `a2a6e66` (test)

**Plan metadata:** final docs commit (SUMMARY / STATE / ROADMAP / REQUIREMENTS).

## Key Artifacts (per plan `<output>` spec)

### Caption-vs-reference discrimination rule
- **Caption** (keep prose): a label at a SEGMENT BOUNDARY (`(?<=^)` line start, or `(?<=[.!?]\s)` just after a sentence terminator) + `\d{1,4}` + `:`/`.` delimiter + a following capital. Strip label+delimiter, keep the sentence.
- **Reference** (remove + repair): a label embedded mid-sentence. Removed as: (a) whole cross-reference parenthetical `\(\s*(?:see|cf\.|e\.g\.|i\.e\.\s+)?<label>\s*\d{1,4}\s*\)`; (b) bare token `<label>\s*\d{1,4}[a-zA-Z]?`; then `_repair_dangling`.

### `_repair_dangling` substitutions (bounded — ReDoS-safe)
```python
re.sub(r"\([^\S\n]{0,8}\)", "", text)     # "( )" / "()" -> ""
re.sub(r"\bin[^\S\n]{1,8},", "in", text)  # "in ," -> "in"
re.sub(r"[^\S\n]{1,8},", ",", text)       # " ," -> ","
# (double-space collapse intentionally left to the final _collapse_whitespace)
```

### Footnote-body conservative pattern + best-effort scope
```python
_FOOTNOTE_BODY_RE = re.compile(r"^\s*(?:\[\d{1,4}\]|\d{1,4}[.)])\s+[A-Z].{20,}$")  # single-line, no DOTALL
```
Dropped only when: a preceding blank line, AND every line of the contiguous run matches. **Best-effort** (no page model post-extraction); the corpus pins only the committed `n.`-form case. Markers always; bodies best-effort (honestly scoped).

### Residual image-artifact patterns (NOT a literal-MD-image matcher)
```python
_IMAGE_ARTIFACT_RE = re.compile(
    r"\b(?:image|img|figure|fig|graphic|illustration|diagram|chart|photo|pic|screenshot)"
    r"\d+\.(?:png|jpe?g|gif|svg|webp|bmp|tiff?)\b", re.IGNORECASE)
```
Note: literal `![alt](img.png)` is parser-stripped before the cleaner runs (md_parser renders → HTML → `get_text()` drops the `<img>`); this catches only a residual filename token. md_parser stays read-only.

### Complete-stage-ordering test
`TestStageOrdering::test_orchestrator_stage_order` — a source-index (`inspect.getsource(clean_text).index()`) comparison, no execution. Pins currency<inline-math, citations<footnote-bodies<captions<code<table/chart, abbreviations<url/email, chart<list-markers, `_collapse_whitespace` last.

### Corpus selector → requirement coverage table (all resolve ≥1 passing test)
| `-k` selector | Requirement | Tests | Flavors exercised |
|---------------|-------------|-------|-------------------|
| `figures` | CLEAN-01 | 6 | PDF/ASCII + EPUB/UTF-8 |
| `headers_footers` | CLEAN-02 | 2 | PDF |
| `footnotes` | CLEAN-03 | 3 | PDF |
| `tables` | CLEAN-04 | 1 | PDF |
| `code_lists_urls` | CLEAN-05 | 5 | TXT |
| `normalization` | CLEAN-06 | 10 | TXT |
| `preserve` | CLEAN-07 | 7 | PDF/TXT, both ascii_only axes |
| (whole file) | CLEAN-08 | 44 | all of the above |

### Planted-regression loud-failure observation (CLEAN-08 / ROADMAP criterion #4)
- **Reverted fix:** re-widened `_remove_page_numbers` to the old blunt `re.sub(r"(?m)^\s*\d{1,4}\s*$", "", text)` (strips every standalone number line).
- **Tests that went RED (3):** `tests/test_cleaner_corpus.py::TestSnapshotsPreserve::test_preserve_snapshot_exact[years_preserve-txt-True]`, `TestPreservationInvariants::test_preserve_year_list`, `tests/test_cleaner.py::TestPageNumbers::test_number_between_prose_preserved`.
- **Observed diff (legible):**
  ```
  E  AssertionError: assert 'Annual sales figures by year:\n\nGrowth continued each year.'
                       == 'Annual sales figures by year:\n\n2019\n2020\n2021\n\nGrowth continued each year.'
       Annual sales figures by year:
     - 2019
     - 2020
     - 2021
       Growth continued each year.
  ```
- **Restore:** the conservative boundary logic was restored byte-for-byte (`git diff diana/processing/cleaner.py` empty vs HEAD); full cleaner+corpus suite green (165 passed). The guard fails loudly on a real quality regression.

## Decisions Made
- See `key-decisions` frontmatter. Most consequential: the `_repair_dangling` ReDoS fix (bounded quantifiers + dropping the non-spec `" ."` substitution) — a self-introduced bug caught by runtime-verifying linearity rather than trusting inspection.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ReDoS / catastrophic backtracking in `_repair_dangling` (self-introduced, fixed within Task 1)**
- **Found during:** Task 1, ReDoS sanity verification (the threat model T-02-01 requires the figure/caption/footnote patterns to run linearly on adversarial input).
- **Issue:** My first `_repair_dangling` draft used unbounded `[^\S\n]+` whitespace runs plus a non-spec `" ."→"."` substitution. Under `re.sub`'s position-by-position scan, `[^\S\n]+\.` (and `[^\S\n]+,`) over a long run of spaces with no following punctuation is **O(n²)** — `paren-bomb` took 36.3 s and `ref-bomb` 9.2 s (vs the required sub-second).
- **Fix:** Bounded every whitespace quantifier to a small cap (`{0,8}`/`{1,8}` — a removed reference leaves only a handful of adjacent spaces; anything larger is healed by the final `_collapse_whitespace`); removed the non-spec `" ."→"."` line entirely (outside RESEARCH's 4-substitution spec); dropped the redundant double-space collapse (the final stage owns it). Re-verified linear: worst 0.03 s on 780k chars.
- **Files modified:** `diana/processing/cleaner.py` (`_repair_dangling`).
- **Commit:** `1f9ea61` (folded into the Task-1 commit, before it landed — the pathological version never reached a commit).

**2. [Rule 2 - Missing critical coverage] EPUB flavor absent from the corpus (added in the Task-3 sweep)**
- **Found during:** Task 3, the CLEAN-08 completeness sweep (the corpus must span "the PDF/EPUB/TXT flavors named in VALIDATION", and CLEAN-01 explicitly concerns EPUB/MD image artifacts).
- **Issue:** Before this plan the corpus carried only `txt` and `pdf` flavors — no `epub` — and ran every snapshot with `ascii_only=True`, so the UTF-8 (`ascii_only=False`) cleaning path was un-snapshotted at corpus level.
- **Fix:** Added `figures_epub` (`source_format="epub"`, `ascii_only=False`) exercising the EPUB image-artifact strip + a caption + an inline reference on the UTF-8-capable side. Coverage-only; no production change (`cleaner.py` byte-identical to the Task-2 commit).
- **Files modified:** `tests/test_cleaner_corpus.py`, `tests/fixtures/cleaner/figures_epub.{in,expected}.txt`.
- **Commit:** `a2a6e66`.

### Note (not a deviation)
- I followed the RESEARCH `_repair_dangling` substitution table verbatim, so the reference case yields `As shown in the trend is up.` (the `in ,`→`in` rule), not the plan-prose illustrative `As shown the trend`. The figures fixture encodes the RESEARCH-spec result and the plan's acceptance one-liner accepts it (it asserts `Figure 3` gone, ` in ,` gone, `trend is up` present).

## Issues Encountered
- **Pre-existing, out-of-scope test failure (unchanged):** `tests/test_llm_client_anthropic_cli.py::test_anthropic_cli_real_call` fails — a live `claude login` / Node CLI end-to-end test, unrelated to the cleaner, already failing on the clean baseline and logged in `deferred-items.md`. NOT fixed (SCOPE BOUNDARY). The full project suite is otherwise green: **349 passed, 1 failed** (only that one); the cleaner+corpus suite is fully green (165 passed; corpus 44 passed).

## Known Stubs
None. `cleaner.py` stays pure-stdlib (`re`/`unicodedata`/`collections`); no new imports, no hardcoded empties, placeholders, or `NotImplementedError` introduced. The footnote-body remover is honestly scoped as best-effort (documented in its docstring), not a stub — it removes the cases it commits to and the corpus pins exactly those.

## Threat Flags
None. No new network/auth/file-path/schema surface — the only trust boundary remains untrusted document/news text → the `re` engine (unchanged from 02-01). The single ReDoS axis (T-02-01) is mitigated by bounded/anchored single-line patterns and is **runtime-verified linear** on adversarial inputs for every new stage (after the Rule-1 fix above).

## Next Phase Readiness
- Phase 2 is functionally complete: all of CLEAN-01..08 are implemented and corpus-guarded. The cleaner is the trustworthy LLM-off primary path the ROADMAP requires.
- The golden corpus now enforces the FULL removal set (pipe-table + no-URL/email + no-figure-token + no-dangling) plus preservation across every snapshot and all three flavors, and the planted-regression check proves it fails loudly — the CLEAN-08 regression-guard intent is demonstrated end-to-end.
- The complete-stage-ordering test will catch any accidental reorder in future cleaner edits.
- No blockers introduced. Phase 3 (Native OS TTS) adds `native_os` to `_ASCII_ONLY_ENGINES` (one line); the cleaner seam already supports it.

## Self-Check: PASSED

- Created fixture files verified on disk (all 6: `figures.{in,expected}.txt`, `footnotes.{in,expected}.txt`, `figures_epub.{in,expected}.txt`) — all FOUND.
- Task commits verified in git log: `1f9ea61`, `5bc75fd`, `a2a6e66` — all FOUND.
- Cleaner + corpus suite: 165 passed; corpus suite: 44 passed; every VALIDATION `-k` selector (`figures`/`headers_footers`/`footnotes`/`tables`/`code_lists_urls`/`normalization`/`preserve`) resolves to ≥1 passing test; full project suite: 349 passed (only the pre-existing, out-of-scope `test_anthropic_cli_real_call` fails, logged in deferred-items.md).
- Planted-regression loud-failure check executed, RED-with-diff observed and recorded above, fix restored byte-for-byte, green re-confirmed.

---
*Phase: 02-rule-based-cleaner-overhaul*
*Completed: 2026-06-01*
