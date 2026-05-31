---
phase: 02
slug: rule-based-cleaner-overhaul
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-31
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `02-RESEARCH.md` § Validation Architecture (runtime-verified).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest` >=7.0 (synchronous; `pytest-asyncio` not needed — the cleaner is sync) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| **Quick run command** | `.venv/bin/pytest tests/test_cleaner.py tests/test_cleaner_corpus.py -q` |
| **Full suite command** | `.venv/bin/pytest -q` |
| **Estimated runtime** | ~1–3 seconds (cleaner tests are pure-stdlib, no I/O) |

> No new test deps: `hypothesis` is **not** installed and is **not** added — invariants are hand-written (verified against `pyproject.toml:38` `dev = ["pytest>=7.0", "pytest-asyncio>=0.23.0"]`).

---

## Sampling Rate

- **After every task commit:** `.venv/bin/pytest tests/test_cleaner.py tests/test_cleaner_corpus.py -q` (sub-second)
- **After every plan wave:** `.venv/bin/pytest -q` (confirms `parsers` / `pipeline` / `summarizer` integrate with the new `clean_text(...)` signature)
- **Before `/gsd:verify-work`:** Full suite must be green, **plus** the manual "loud-failure" check (see Manual-Only Verifications) to satisfy ROADMAP criterion #4
- **Max feedback latency:** ~3 seconds

---

## Per-Task Verification Map

> Task IDs are assigned during planning (VALIDATION.md is created before PLAN.md per the
> GSD flow). The **requirement → test** coverage below is fixed now; the planner/executor
> binds each task to the matching `pytest -k` selector, and `/gsd:validate-phase` fills the
> per-task rows after plans exist.

| Requirement | Behavior under test | Test Type | Automated Command (`-k` selector) | File Exists | Status |
|-------------|---------------------|-----------|-----------------------------------|-------------|--------|
| CLEAN-01 | Caption label stripped + prose kept; inline fig ref removed + grammar repaired; EPUB/MD image artifacts gone | snapshot + invariant | `pytest tests/test_cleaner_corpus.py -k figures -q` | ❌ W0 | ⬜ pending |
| CLEAN-02 | Page numbers stripped at boundary only; years/chapters kept; format-aware | snapshot + invariant | `pytest tests/test_cleaner_corpus.py -k headers_footers -q` | ❌ W0 | ⬜ pending |
| CLEAN-03 | `[n]` + superscript markers removed; footnote bodies best-effort; numbered lists kept | snapshot + invariant | `pytest tests/test_cleaner_corpus.py -k footnotes -q` | ❌ W0 | ⬜ pending |
| CLEAN-04 | ≥2-row table block removed silently; lone numeric sentence kept | snapshot + invariant | `pytest tests/test_cleaner_corpus.py -k tables -q` | ❌ W0 | ⬜ pending |
| CLEAN-05 | Code fences/indented code removed; list markers stripped (text kept); URLs/emails removed; `U.S.`/`e.g.` kept | snapshot + invariant | `pytest tests/test_cleaner_corpus.py -k code_lists_urls -q` | ❌ W0 | ⬜ pending |
| CLEAN-06 | `$5`→"5 dollars", `$5.50`→"5 dollars and 50 cents", `50%`→"50 percent", `Dr.`→"Doctor"; `$5 and $10` both survive | snapshot + invariant | `pytest tests/test_cleaner_corpus.py -k normalization -q` | ❌ W0 | ⬜ pending |
| CLEAN-07 | café→café (UTF-8) / café→cafe (ASCII), never `caf`; headings/years/short non-noise kept | invariant (both directions, `ascii_only` parametrized) | `pytest tests/test_cleaner_corpus.py -k preserve -q` | ❌ W0 | ⬜ pending |
| CLEAN-08 | The suite exists and fails loudly on a planted regression | meta | `pytest tests/test_cleaner_corpus.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cleaner_corpus.py` — two-layer suite (property invariants + snapshot fixtures), covers CLEAN-01..08
- [ ] `tests/fixtures/cleaner/` — synthetic input/expected pairs, one per CLEAN-0x concern, PDF/EPUB/TXT flavors
- [ ] Update `tests/test_cleaner.py` — the tests encoding **buggy** behavior (see RESEARCH § Regression Flags: `test_accented_chars_removed`, `test_standalone_number_removed`, `test_prose_with_numbers_preserved`) flip to new expectations **in the same commit** as the fix (RED→GREEN within the slice)
- [ ] No framework install needed (`pytest` present; no `hypothesis`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Suite "fails loudly" on quality regression | CLEAN-08 / ROADMAP criterion #4 | Proving a *guard* works requires deliberately introducing a regression — not something the green suite asserts about itself | Temporarily revert one fix (e.g. re-widen `_remove_page_numbers` to the old `^\s*\d{1,4}\s*$`), run the quick command, confirm a corpus test goes **red with a legible diff**, then restore. Record the observed failure. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`tests/test_cleaner_corpus.py`, `tests/fixtures/cleaner/`)
- [ ] No watch-mode flags
- [ ] Feedback latency < 3s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
