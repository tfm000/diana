---
phase: 02-rule-based-cleaner-overhaul
plan: 03
subsystem: processing
tags: [cleaner, tts, code-blocks, list-markers, urls, emails, regex, redos, pytest, golden-corpus]

# Dependency graph
requires:
  - phase: 02-rule-based-cleaner-overhaul
    plan: 01
    provides: "clean_text(text, *, source_format=None, ascii_only=False) keyword-only seam; line-oriented split/keep/join idiom (_remove_tables); chart/heading protection (_remove_chart_fragments + _SECTION_WORDS); the two-layer golden-corpus harness (_invariants + snapshot loader) with the 'Wave N adds' extension contract"
  - phase: 02-rule-based-cleaner-overhaul
    plan: 02
    provides: "_expand_abbreviations (runs BEFORE URL/email so e.g./i.e. are words by stage 13); the existing _strip_urls https?:// helper this plan extends; the normalization corpus fixtures the no-URL/no-email invariant now also sweeps"
provides:
  - "_remove_code_blocks: fenced (``` … ```) span removal via a BOUNDED DOTALL pattern + contiguous 2+ line indented (4-space/tab) block removal; a SINGLE indented line is KEPT (CLEAN-07 over-strip guard). Wired BEFORE _remove_tables/_remove_chart_fragments (code looks like noise)."
  - "_strip_list_markers: anchored strip of - / * / + / 1. / a) markers keeping the item PROSE (line never deleted). Wired AFTER _remove_chart_fragments so the chart/heading protection still sees the markers."
  - "_strip_urls extended with a bounded \\bwww\\.\\S+ pass (in addition to https?://\\S+); URLs removed, NOT replaced with a link token."
  - "_strip_emails via bounded module-level _EMAIL_RE = re.compile(r'\\b[\\w.+-]+@[\\w-]+\\.[\\w.-]+\\b'); wired at stage 13 after _expand_abbreviations."
  - "Structural U.S./e.g. guard: the required scheme/www. prefix and required @ mean dotted prose tokens (no scheme, no @) survive the URL/email pass."
  - "no-URL/no-email removal invariant registered into tests/test_cleaner_corpus.py _invariants at the 'Wave N adds' point; holds across ALL committed snapshots."
  - "code_lists_urls + urls_emails_guard corpus fixtures + TestSnapshotsCodeListsUrls so `pytest tests/test_cleaner_corpus.py -k code_lists_urls` resolves (CLEAN-05 selector)."
affects: [02-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Code-before-noise hard ordering: _remove_code_blocks runs before the table/chart detectors so short symbol-heavy code lines never false-trigger them."
    - "List-marker strip AFTER chart-fragment detection so the chart/heading protection (02-01) still sees the markers; the line is never deleted, only the marker prefix."
    - "Fenced-block removal uses a bounded inner match (``` then a negated-fence run then ```), NOT a nested unbounded .* — mirrors _remove_latex_display's DOTALL idiom while staying ReDoS-safe (T-02-01)."
    - "URL/email removal is structural-guard, not allow-list: the required scheme/www. prefix and required @ are what make U.S./e.g. safe — no special-casing of dotted prose tokens."
    - "Incremental corpus contract: THIS wave owns + registers the no-URL/no-email removal invariant into _invariants; the figure/footnote-token invariant stays deferred to 02-04."

key-files:
  created:
    - "tests/fixtures/cleaner/code_lists_urls.in.txt / .expected.txt"
    - "tests/fixtures/cleaner/urls_emails_guard.in.txt / .expected.txt"
  modified:
    - "diana/processing/cleaner.py"
    - "tests/test_cleaner.py"
    - "tests/test_cleaner_corpus.py"

key-decisions:
  - "Used the RESEARCH/PLAN stage positions verbatim — code-block removal at step 8 (before table/chart), list-marker strip at step 14 (after chart detection), URL/email at step 13 (after abbreviations) — no deviation needed."
  - "Combined RED test + GREEN implementation into one commit per task (each task is tdd=true as a single behavioral unit; the plan defines two atomic tasks, not separate RED/GREEN commits) — RED was run and observed failing before each GREEN."
  - "Single indented line is KEPT; only a CONTIGUOUS run of 2+ indented lines is removed — the conservative CLEAN-07 reading (a lone indented line is far more likely prose: a quote, a wrapped sentence, a hanging indent)."
  - "Emails removed via a module-level compiled _EMAIL_RE (mirrors 02-02's _INLINE_MATH_RE pattern) for a single bounded anchored shape; the required @ is the structural guard, not a U.S./e.g. denylist."
  - "Two fixtures (code_lists_urls for the code/list mechanics + the single-indented-prose keep; urls_emails_guard for http/www/email removal with the U.S./e.g. survival), both reached by the -k code_lists_urls class-name token."

patterns-established:
  - "Any new pattern over untrusted document text is bounded/anchored with negated classes (no nested unbounded repetition) — ReDoS mitigation, asserted in acceptance criteria and runtime-verified linear."
  - "Removal stages substitute to the empty string (never a placeholder/link token) per Decision 4."

requirements-completed: [CLEAN-05]

# Metrics
duration: 5min
completed: 2026-06-01
---

# Phase 2 Plan 03: Code Blocks / List Markers / URLs & Emails Summary

**Handled the three remaining mechanical noise classes for natural speech (CLEAN-05): removes fenced + contiguous-indented code blocks (before the table/chart detectors so code never false-triggers them) while KEEPING a lone indented prose line, strips list markers (`- `/`* `/`1. `/`a) `) after chart detection while keeping the item text, and removes URLs (http(s) + www.) and emails entirely — with a structural guard (required scheme/www. prefix, required `@`) so `U.S.`/`e.g.` survive — then registered the no-URL/no-email removal invariant into the golden corpus where it now holds across every snapshot.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-01T00:04:03Z
- **Completed:** 2026-06-01T00:09:09Z
- **Tasks:** 2 (both `type="auto" tdd="true"`)
- **Files modified/created:** 7 (3 modified + 4 fixture files; all committed)

## Accomplishments

- **Code-block removal (CLEAN-05), placed before noise detection:** `_remove_code_blocks` removes fenced ```` ``` ```` blocks via a bounded `re.DOTALL` span (mirrors `_remove_latex_display`) and contiguous runs of 2+ lines indented by 4+ spaces or a tab (line-oriented split/keep/join, mirrors `_remove_tables`). It is wired into `clean_text` BEFORE `_remove_tables`/`_remove_chart_fragments` — code lines are short and symbol-heavy and would false-trigger those detectors if they ran first. The noise-detector tests (`TestChartFragments`, `TestTableRemoval`) stayed green, proving the code-before-noise ordering did not regress them.
- **The CLEAN-07 over-strip guard holds:** a SINGLE indented line is KEPT (only a contiguous 2+ line run is removed) — `"Normal line.\n    This indented sentence is prose, not code.\nNext line."` keeps the indented sentence. A lone indented line is far more likely prose (a quote, a wrapped sentence, a hanging indent) than code.
- **List-marker strip (CLEAN-05), placed after chart detection:** `_strip_list_markers` strips a leading `- `/`* `/`+ ` bullet, `1. `/`12. ` ordered-numeric, or `a) `/`A) ` ordered-alpha marker and keeps the remaining item PROSE — the line is never deleted. It is wired AFTER `_remove_chart_fragments` (hard constraint: the chart/heading protection from 02-01 must still see the markers to protect list items; stripping earlier would blind it). `- Apples` → `Apples`, `1. First step` → `First step`.
- **URL + email removal (CLEAN-05), removed entirely (not "link"):** `_strip_urls` gained a second bounded `\bwww\.\S+` pass alongside the existing `https?://\S+`; `_strip_emails` removes clear emails via a bounded module-level `_EMAIL_RE`. Both run at stage 13 AFTER `_expand_abbreviations` (stage 12). URLs/emails are removed, never replaced with a "link" token (Decision 4) — both removers substitute the empty string.
- **The `U.S.`/`e.g.` guard is structural, not a denylist:** the URL pattern requires a scheme or `www.` prefix and the email pattern requires an `@`, so `U.S.` (no scheme, no `@`) survives and `e.g.` — already expanded to "for example" by 02-02 before this pass — survives uneaten. Asserted directly (`test_us_abbreviation_not_mistaken_for_url`, `test_eg_expansion_survives_url_pass`).
- **no-URL/no-email invariant registered + corpus coverage (CLEAN-05):** registered `assert "http" not in out and "www." not in out and not re.search(r"\S+@\S+\.\S+", out)` into `tests/test_cleaner_corpus.py`'s `_invariants` at the "Wave N adds" extension point — this is the wave that owns it per the incremental contract. It now sweeps across ALL committed snapshots and passes (no prior fixture planted a URL/email, as predicted). Added two fixtures (`code_lists_urls`, `urls_emails_guard`) and `TestSnapshotsCodeListsUrls` so `pytest tests/test_cleaner_corpus.py -k code_lists_urls` resolves (5 passed). Did NOT add the figure-reference-token invariant — that stays 02-04's to register.
- **ReDoS posture (T-02-01):** all four new/extended patterns are bounded/anchored with negated classes — the fenced span uses `` ```[^\n`]*\n(?:[^`]|`(?!``))*``` `` (no nested unbounded `.*`), indented-code and list-marker tests are anchored line-oriented (`^( {4,}|\t)`, `^\s*[-*+]\s+`, `^\s*\d{1,3}[.)]\s+`, `^\s*[A-Za-z][.)]\s+`), the www. pass runs `\S+` only after a required prefix, and `_EMAIL_RE` is anchored negated-class. Runtime sanity (all linear): fenced unclosed 200k → 0.0008s; 50k indented-run → 0.0096s; 50k list-markers → 0.0137s; www. 200k → 0.0003s; email no-dot 200k → 0.0016s; 50k emails → 0.0039s.

## Task Commits

Each task committed atomically (TDD: RED check run and observed failing before each GREEN implementation):

1. **Task 1: Code-block removal (before table/chart) + list-marker strip (after chart detection) — CLEAN-05** — `ab64917` (feat)
2. **Task 2: URL + email removal with U.S./e.g. guard + code_lists_urls corpus coverage + register no-URL/no-email invariant — CLEAN-05** — `c9e816d` (feat)

**Plan metadata:** (final docs commit — SUMMARY/STATE/ROADMAP/REQUIREMENTS)

## Key Artifacts (per plan `<output>` spec)

### Final stage order around code / lists / URL / email (the `clean_text` body)
```
_remove_citations
_remove_figure_table_refs
_remove_code_blocks              (8)    # <-- NEW; BEFORE table/chart (code looks like noise)
_remove_tables
_remove_chart_fragments
_strip_list_markers              (14)   # <-- NEW; AFTER chart detection (protection needs the markers)
_remove_common_footers
_expand_abbreviations            (12)
_strip_urls                      (13)   # <-- extended with www.; removes entirely (no "link")
_strip_emails                    (13)   # <-- NEW; bounded _EMAIL_RE; AFTER abbreviations
_normalize_unicode
…
```
Hard constraints honored: (8) code **before** (9)(10) table/chart; (10) chart-fragment **before** (14) list-marker strip; (12) abbreviations **before** (13) URL/email.

### Code-fence / indented-code detection approach
- **Fenced:** `re.sub(r"```[^\n`]*\n(?:[^`]|`(?!``))*```", "", text, flags=re.DOTALL)` — language tag tolerated on the open fence (`[^\n`]*`), bounded inner run (a non-backtick char, or a backtick not starting a closing fence). Removed regardless of length (the fence markers are unambiguous).
- **Indented:** line-oriented; a CONTIGUOUS run where `re.match(r"^( {4,}|\t)", line)` holds for ≥2 lines is dropped. A SINGLE such line is KEPT (the over-strip guard).

### List-marker patterns (item PROSE kept; line never deleted)
```python
re.sub(r"^\s*[-*+]\s+", "", line)          # bullets: - * +
re.sub(r"^\s*\d{1,3}[.)]\s+", "", line)    # ordered-numeric: 1. / 12. / 1)
re.sub(r"^\s*[A-Za-z][.)]\s+", "", line)   # ordered-alpha: a) / A. / b)
```
First match wins (bullet → numeric → alpha), applied per line.

### URL / email patterns + the structural U.S./e.g. guard
```python
# _strip_urls
re.sub(r"https?://\S+", "", text)
re.sub(r"\bwww\.\S+", "", text)
# _strip_emails
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
```
**Guard is structural:** the URL pattern needs a scheme or `www.` prefix; the email pattern needs an `@`. `U.S.` has neither → kept. `e.g.` is already "for example" by stage 13 (02-02 expands it before this) → kept.

### no-URL/no-email invariant (registered into `_invariants`, Wave-3 extension point)
```python
assert "http" not in out, f"URL leaked: {out!r}"
assert "www." not in out, f"www. URL leaked: {out!r}"
assert not re.search(r"\S+@\S+\.\S+", out), f"email leaked: {out!r}"
```
Holds across every committed snapshot (swept by `TestInvariantsAcrossSnapshots` + the per-class invariant tests).

### `code_lists_urls` corpus cases added (`-k code_lists_urls`)
| Fixture | exercises (ascii_only=True, source_format=txt) |
|---------|-----------------------------------------------|
| `code_lists_urls` | fenced ```` ```python ```` block removed; `- `/`1. ` markers stripped with item text kept (Apples/Oranges/First step/Second step); single 4-space-indented prose line KEPT |
| `urls_emails_guard` | `https://…/x` + `www.foo.org` removed; two emails (incl. `jane.doe+news@sub.example.co.uk`) removed; `U.S.` kept; `e.g.`→"for example" survives |

Each is exercised as an exact snapshot match AND through the cross-stage `_invariants` sweep (now including the no-URL/no-email removal invariant this wave registered).

## Decisions Made
- See `key-decisions` frontmatter. Most consequential: the U.S./e.g. guard is **structural** (required scheme/www. prefix + required `@`), not a denylist of dotted tokens — so it generalizes to any dotted prose (`i.e.`, `et al.`, initials) without enumeration, and it composes with 02-02's abbreviation expansion (which has already turned `e.g.` into words before stage 13).

## Deviations from Plan

None — plan executed exactly as written. The RESEARCH/PLAN stage positions and bounded-pattern shapes dropped in cleanly; no auto-fixes (Rules 1–3) and no architectural questions (Rule 4) were triggered.

*(Note: one acceptance-criteria self-check one-liner I wrote initially over-matched the literal word "link" inside the `_strip_urls` docstring ("NOT replaced with a 'link' token"). That was a flaw in my check string, not the code — the real criterion ("no `\"link\"` substitution in the helpers") holds: every `re.sub` in both removers replaces with the empty string, and `test_url_removed_not_replaced_with_link` / `test_email_not_replaced_with_link` assert it behaviorally and pass. Not a code deviation.)*

## Issues Encountered
- **Pre-existing, out-of-scope test failure (unchanged):** `tests/test_llm_client_anthropic_cli.py::test_anthropic_cli_real_call` fails — a live `claude login`/Node CLI end-to-end test, unrelated to the cleaner, already failing on the clean baseline and logged in `deferred-items.md`. NOT fixed (SCOPE BOUNDARY). The full project suite is otherwise green: **325 passed, 1 failed (that one)**; the cleaner+corpus suite is fully green (141 passed).

## Known Stubs
None. The cleaner stays pure-stdlib (`re`/`unicodedata`/`collections`) and deterministic; no hardcoded empties, placeholders, or `NotImplementedError` introduced.

## Threat Flags
None. No new network/auth/file-path/schema surface — the only trust boundary remains untrusted document/news text → the `re` engine (unchanged from 02-01). The single ReDoS axis (T-02-01) is mitigated by bounded/anchored patterns and asserted in the acceptance criteria + runtime-verified linear on adversarial inputs.

## Next Phase Readiness
- The code-block, list-marker, URL, and email stages are now in `clean_text` at the proven stage positions. **02-04** (figure/footnote/LaTeX, CLEAN-01/03) builds directly on this body and must append the no-figure/table-reference-token invariant at the `_invariants` "Wave N adds" extension point AS it lands that stage (this wave deliberately registered only the no-URL/no-email invariant).
- The `_invariants` set now actively enforces no-URL / no-www. / no-email across every snapshot, so any future fixture that plants one will fail loudly — exactly the CLEAN-08 regression-guard intent.
- No blockers introduced.

## Self-Check: PASSED

- Created fixture files verified on disk (all 4: `code_lists_urls.in.txt`/`.expected.txt`, `urls_emails_guard.in.txt`/`.expected.txt`) — all FOUND.
- Task commits verified in git log: `ab64917`, `c9e816d` — both FOUND.
- Cleaner + corpus suite: 141 passed; `-k code_lists_urls` selector: 5 passed; full project suite: 325 passed (only the pre-existing, out-of-scope `test_anthropic_cli_real_call` fails, logged in deferred-items.md).

---
*Phase: 02-rule-based-cleaner-overhaul*
*Completed: 2026-06-01*
