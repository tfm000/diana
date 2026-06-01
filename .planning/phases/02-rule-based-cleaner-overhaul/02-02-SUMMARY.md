---
phase: 02-rule-based-cleaner-overhaul
plan: 02
subsystem: processing
tags: [cleaner, tts, normalization, currency, percent, abbreviations, regex, redos, pytest, golden-corpus]

# Dependency graph
requires:
  - phase: 02-rule-based-cleaner-overhaul
    plan: 01
    provides: "clean_text(text, *, source_format=None, ascii_only=False) keyword-only seam; the existing inline-math remover (back half of _remove_remaining_latex); the two-layer golden-corpus harness (_invariants + snapshot loader) with the 'Wave N adds' extension contract"
provides:
  - "_normalize_currency_percent: $5->5 dollars, $5.50->5 dollars and 50 cents, 50%->50 percent, £10->10 pounds, €20->20 euros (digits preserved, no number-to-words)"
  - "Math-aware _remove_inline_math (replaces the bare $...$ remover) using a bounded module-level _INLINE_MATH_RE = re.compile(r'\\$([^$\\n]{1,200}?)\\$') — drops a $-span only on a math signal, keeps stray-command/brace stripping"
  - "Load-bearing stage order: _normalize_currency_percent (3) runs BEFORE _remove_inline_math (4) so '$5 and $10' both survive"
  - "_ABBREVIATIONS curated map + _expand_abbreviations with (?<![A-Za-z]) lookbehind + required trailing period (no mid-word, no bare-token false matches), wired BEFORE _strip_urls"
  - "5 normalization corpus fixtures + TestSnapshotsNormalization so 'pytest tests/test_cleaner_corpus.py -k normalization' resolves (CLEAN-06 selector)"
  - "Regression #3 flipped: TestTableRemoval::test_prose_with_numbers_preserved asserts '95 percent'"
affects: [02-03, 02-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Symbol->word normalization as ordered re.sub substitutions (cents form before bare-dollar form so $5.50 is not partially consumed)"
    - "Currency-before-inline-math hard ordering: convert every currency $ to words first so the math-aware $-remover never mis-pairs a currency span"
    - "Math-vs-currency discrimination via an inner-text math-signal guard ([A-Za-z\\^_=+<>/]) on a bounded {1,200} negated-class span (ReDoS-safe, T-02-01)"
    - "Curated abbreviation expansion via a module map + (?<![A-Za-z]) lookbehind loop (mirrors the _GREEK_LETTERS map+loop, but re.sub word-boundary-safe not bare .replace())"
    - "Incremental corpus contract honored: this wave's transforms add fixtures + run the existing Wave-2 _invariants over them, but register NO new removal invariant (no-URL/email and figure-token stay deferred to 02-03/02-04)"

key-files:
  created:
    - "tests/fixtures/cleaner/currency_dollars.in.txt / .expected.txt"
    - "tests/fixtures/cleaner/currency_cents.in.txt / .expected.txt"
    - "tests/fixtures/cleaner/currency_dual.in.txt / .expected.txt"
    - "tests/fixtures/cleaner/percent_normalize.in.txt / .expected.txt"
    - "tests/fixtures/cleaner/abbreviations_expand.in.txt / .expected.txt"
  modified:
    - "diana/processing/cleaner.py"
    - "tests/test_cleaner.py"
    - "tests/test_cleaner_corpus.py"

key-decisions:
  - "Used the RESEARCH Q3/Q4 runtime-verified bodies verbatim (currency substitution order cents-first; _INLINE_MATH_RE bounded {1,200}; abbreviation lookbehind) — no deviation needed"
  - "Combined RED test + GREEN implementation into one commit per task (each task is tdd=true as a single behavioral unit; the plan defines two atomic tasks, not separate RED/GREEN commits) — RED was run and observed failing before each GREEN"
  - "normalization fixtures are tagged by stem prefix (currency_/percent_/abbreviations_) and exposed via a TestSnapshotsNormalization class whose name carries the 'normalization' token so the VALIDATION -k selector resolves to it"
  - "No new removal invariant registered in _invariants this wave (currency/abbreviation are transforms); the existing Wave-2 _invariants run cross-stage over the new fixtures per the incremental contract"

patterns-established:
  - "Symbol->word normalization runs before the destructive $-span remover; the remover keeps a math-signal guard as defense-in-depth"
  - "Bounded-quantifier + negated-class regex for any new pattern over untrusted document text (ReDoS mitigation, asserted in acceptance criteria)"

requirements-completed: [CLEAN-06]

# Metrics
duration: 4min
completed: 2026-05-31
---

# Phase 2 Plan 02: Spoken Normalization (Currency / Percent / Abbreviations) Summary

**Added currency/percent symbol→word conversion that runs BEFORE a new bounded math-aware inline-math remover (so `$5 and $10` both survive while real `$x + y$` is still removed), plus a curated low-ambiguity abbreviation-expansion table, flipped Regression #3 to `95 percent`, and stood up the `normalization` corpus selector — satisfying CLEAN-06 without spelling any digit to words.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-31T23:55:23Z
- **Completed:** 2026-05-31T23:59:28Z
- **Tasks:** 2 (both `type="auto" tdd="true"`)
- **Files modified/created:** 13 (3 modified + 10 fixture files; all committed)

## Accomplishments

- **Currency/percent symbol→word (CLEAN-06, the spoken-normalization slice):** `_normalize_currency_percent` converts `$5`→"5 dollars", `$5.50`→"5 dollars and 50 cents", `$1,000`→"1,000 dollars", `50%`→"50 percent" (incl. `3.5%`→"3.5 percent" and a space-tolerant `50 %`), `£10`→"10 pounds", `€20`→"20 euros". Digits are preserved verbatim — only the symbol becomes a word (no number-to-words; VNEXT-03 stays deferred and the TTS engine vocalizes the digits).
- **Killed the `$5 and $10` currency-loss bug (the single load-bearing ordering constraint):** the old `re.sub(r"\$[^$]*?\$", "", text)` paired the first `$` with the next, so `"I paid $5 and $10 for lunch."` → `"I paid 10 for lunch."`. Now `_normalize_currency_percent` (stage 3) runs BEFORE the inline-math remover (stage 4), removing every `$` first, so nothing mis-pairs — both `5 dollars` and `10 dollars` survive (asserted directly in Task 1's automated verify, not only via the LaTeX classes).
- **Math-aware inline-math remover (replaces the buggy line):** `_remove_inline_math` uses a module-level bounded `_INLINE_MATH_RE = re.compile(r"\$([^$\n]{1,200}?)\$")` and drops a `$`-span only when its inner text carries a math signal (`[A-Za-z\^_=+<>/]`), else keeps it (defense-in-depth). Real `$x + y$` is still removed. The stray-command (`\textbf{...}`→content, other `\command`→removed) and stray-brace stripping from the old `_remove_remaining_latex` were folded into the new helper so `TestRemainingLatexRemoval` stays green.
- **Curated abbreviation expansion (CLEAN-06):** `_ABBREVIATIONS` (11 entries) + `_expand_abbreviations` expand `Dr.`→Doctor, `Mr.`→Mister, `Mrs.`→Missus, `Ms.`→Miz, `Prof.`→Professor, `e.g.`→"for example", `i.e.`→"that is", `etc.`→"et cetera", `vs.`→"versus", `approx.`→"approximately", `cf.`→"compare". A `(?<![A-Za-z])` lookbehind blocks mid-word matches (`Drone.` stays `Drone.`) and the required trailing period blocks bare tokens (the word `Mr` alone stays). Ambiguous units (`m`/`kg`/`mi`) and `St.` (Saint vs Street) are intentionally left to the engine, honoring the no-over-expansion criterion. Wired BEFORE `_strip_urls` so dotted tokens are already words before any later URL pass (02-03).
- **Regression #3 flipped + corpus coverage:** `TestTableRemoval::test_prose_with_numbers_preserved` now asserts `"95 percent"` (was `"95%"`). Added 5 `normalization` snapshot fixtures and `TestSnapshotsNormalization` so `pytest tests/test_cleaner_corpus.py -k normalization` resolves (10 passed); the existing Wave-2 `_invariants` run cross-stage over the new inputs (no new removal invariant added — currency/abbreviation are transforms, per the incremental contract).
- **ReDoS posture (T-02-01):** the new `_INLINE_MATH_RE` is a bounded `{1,200}` quantifier over a negated `[^$\n]` class (no nested unbounded repetition); the 11 abbreviation patterns are literal escaped-dot tokens behind a fixed lookbehind. Runtime sanity: 100k adversarial `$`+`a` input cleaned in 0.0137s; 50k bare `$` in 0.0004s (linear).

## Task Commits

Each task committed atomically (TDD: RED check run and observed failing before each GREEN implementation):

1. **Task 1: Currency/percent symbol→word (before inline-math) + math-aware inline-math remover** — `07d95ad` (feat)
2. **Task 2: Curated abbreviation expansion + normalization corpus coverage (flip Regression #3)** — `87194fd` (feat)

**Plan metadata:** (final docs commit — SUMMARY/STATE/ROADMAP/REQUIREMENTS)

## Key Artifacts (per plan `<output>` spec)

### Final stage order around currency / inline-math (the `clean_text` body)
```
_remove_latex_display            (1)
_simplify_latex_inline           (2)   # runs while $-spans intact
_normalize_currency_percent      (3)   # <-- NEW; MUST precede inline-math
_remove_inline_math              (4)   # <-- NEW math-aware remover (+ stray cmd/brace)
_remove_citations                (5)
_remove_figure_table_refs        (…)
_remove_tables
_remove_chart_fragments
_remove_common_footers
_expand_abbreviations            (12)  # <-- NEW; BEFORE _strip_urls
_strip_urls
_normalize_unicode
_remove_repeated_lines
_remove_page_numbers(source_format)
_transliterate_ascii  / strip_non_speakable   # only if ascii_only
_collapse_whitespace             (last)
```
Hard constraints honored: (3) currency **before** (4) inline-math; (12) abbreviations **before** URL strip.

### `_INLINE_MATH_RE`
```python
_INLINE_MATH_RE = re.compile(r"\$([^$\n]{1,200}?)\$")   # bounded -> no ReDoS (T-02-01)
```

### `_ABBREVIATIONS` map contents
```python
_ABBREVIATIONS = {
    r"Dr\.": "Doctor", r"Mr\.": "Mister", r"Mrs\.": "Missus", r"Ms\.": "Miz",
    r"Prof\.": "Professor", r"e\.g\.": "for example", r"i\.e\.": "that is",
    r"etc\.": "et cetera", r"vs\.": "versus", r"approx\.": "approximately",
    r"cf\.": "compare",
}
```
Applied as `re.sub(r"(?<![A-Za-z])" + pat, rep, text)`. Deliberately excludes `m`/`kg`/`mi`/`St.` (engine handles those).

### `$5 and $10` — before / after
- **Before this plan:** `"I paid $5 and $10 for lunch."` → `"I paid 10 for lunch."` (the `$5 and $` span was eaten by the old `$...$` remover; `$5` and currency lost).
- **After this plan:** `"I paid $5 and $10 for lunch."` → `"I paid 5 dollars and 10 dollars for lunch."` (currency converted first; nothing mis-pairs).
- **Real math still removed:** `"Before $x + y$ after"` → `"Before after"`.

### normalization corpus cases added (`-k normalization`)
| Fixture | input | expected (ascii_only=True, source_format=txt) |
|---------|-------|------------------------------------------------|
| `currency_dollars` | `I paid $5 for lunch.` | `I paid 5 dollars for lunch.` |
| `currency_cents` | `The book was $5.50 at the store.` | `The book was 5 dollars and 50 cents at the store.` |
| `currency_dual` | `I paid $5 and $10 for lunch.` | `I paid 5 dollars and 10 dollars for lunch.` (both-survive) |
| `percent_normalize` | `Sales rose 50% last year.` | `Sales rose 50 percent last year.` |
| `abbreviations_expand` | `Dr. Smith and Mr. Jones met, e.g. for lunch.` | `Doctor Smith and Mister Jones met, for example for lunch.` |

Each is exercised both as an exact snapshot match AND through the cross-stage `_invariants` sweep (Wave-2-active subset: no pipe-table row, no dangling ` ,`/`( )`/double-space/triple-newline, ASCII when `ascii_only`).

## Decisions Made
- See `key-decisions` frontmatter. Most consequential: kept the RESEARCH Q3 substitution **order** (cents form `$5.50` before bare-dollar `$5`) so `$5.50` is not partially matched as `$5` — and relied on currency-conversion-first (not the math-signal guard alone) to fix `$5 and $10`, because the guard alone still destroys it (the inner `"5 and "` contains "a" → matches the math signal). This is the phase's load-bearing ordering constraint and it is now enforced in the body.

## Deviations from Plan

None — plan executed exactly as written. The runtime-verified RESEARCH Q3/Q4 bodies dropped in cleanly; no auto-fixes (Rules 1–3) and no architectural questions (Rule 4) were triggered. Regression #3 flip was an explicit, scheduled change (Task 2 acceptance criterion), not a deviation.

## Issues Encountered
- **Pre-existing, out-of-scope test failure (unchanged):** `tests/test_llm_client_anthropic_cli.py::test_anthropic_cli_real_call` fails — a live `claude login`/Node CLI end-to-end test, unrelated to the cleaner, already failing on the clean baseline and logged in `deferred-items.md`. NOT fixed (SCOPE BOUNDARY). The full project suite is otherwise green: **301 passed, 1 failed (that one)**; the cleaner+corpus suite is fully green (117 passed).

## Known Stubs
None. The cleaner stays pure-stdlib (`re`/`unicodedata`/`collections`) and deterministic; no hardcoded empties, placeholders, or `NotImplementedError` introduced.

## Threat Flags
None. No new network/auth/file-path/schema surface — the only trust boundary remains untrusted document/news text → the `re` engine (unchanged from 02-01). The single ReDoS axis (T-02-01) is mitigated by bounded patterns and asserted in the acceptance criteria.

## Next Phase Readiness
- The currency→words and math-aware-inline stages, plus the abbreviation stage (placed before URL stripping), are now in `clean_text`. **02-03** (URL/email stripping, CLEAN-05) and **02-04** (figure/footnote/LaTeX, CLEAN-01/03) build directly on this body and must append their removal invariants at the `_invariants` "Wave N adds" extension point AS they land each stage (this wave deliberately added none — currency/abbreviation are transforms).
- The `e.g.`/`i.e.`/`vs.` dotted tokens are already expanded to words before the URL pass, so a later email/`www.` stripper will not see them as host-like fragments.
- No blockers introduced.

## Self-Check: PASSED

- Created fixture files verified on disk (all 10 normalization `.in.txt`/`.expected.txt`): currency_dollars, currency_cents, currency_dual, percent_normalize, abbreviations_expand — all FOUND.
- Task commits verified in git log: `07d95ad`, `87194fd` — both FOUND.
- Cleaner + corpus suite: 117 passed; `-k normalization` selector: 10 passed; full project suite: 301 passed (only the pre-existing, out-of-scope `test_anthropic_cli_real_call` fails, logged in deferred-items.md).

---
*Phase: 02-rule-based-cleaner-overhaul*
*Completed: 2026-05-31*
