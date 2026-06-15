---
phase: 04
slug: engine-management-voice-catalog
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-15
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from 04-RESEARCH.md "Validation Architecture". Per-task rows are at requirement
> granularity until the planner assigns task IDs; the executor refines Task ID + Status.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7+ with `pytest-asyncio` (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_downloader.py tests/test_catalog.py tests/test_install_state.py tests/test_voice_import.py tests/test_voice_labels.py tests/test_uninstall.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -q` (baseline: 379 passed / 2 skipped) |
| **Estimated runtime** | ~3 seconds (pure-logic units; `network`-marked tests excluded by default) |

*All pytest/python runs MUST use the project `.venv` (per user memory: "Use .venv for Python work"). Worktree executors invoke the absolute `/Users/tyler/Repos/diana/.venv/bin/python -m pytest`.*

---

## Sampling Rate

- **After every task commit:** Run the **Quick run command** (pure-logic units — fast, no network).
- **After every plan wave:** Run the **Full suite command** (green; `network`-marked excluded).
- **Before `/gsd:verify-work`:** Full suite green + the Manual-Only Streamlit checklist below.
- **Max feedback latency:** ~3 seconds.

---

## Per-Task Verification Map

| Req / Behavior | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|----------------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| Manifest parse → TTSVoice + footprint + URL | W0/1 | VOICE-01 | — | typed manifest fields validated before use | unit | `pytest tests/test_catalog.py::test_parse_manifest_entry -x` | ❌ W0 | ⬜ pending |
| Curated-vs-show-all + group-by-language | 1 | VOICE-01 | — | N/A | unit | `pytest tests/test_catalog.py::test_curated_subset -x` | ❌ W0 | ⬜ pending |
| Resume offset: `.part` size N → `Range: bytes=N-`; 206 append / 200 reset | W0/1 | ENGINE-02 | T-04-DL | no partial-file corruption on Range-ignored | unit | `pytest tests/test_downloader.py::test_resume_offset -x` | ❌ W0 | ⬜ pending |
| md5 mismatch → delete `.part`, raise | 1 | ENGINE-02 | T-04-INT | integrity verify before install | unit | `pytest tests/test_downloader.py::test_md5_mismatch_rejects -x` | ❌ W0 | ⬜ pending |
| md5 match → atomic `os.replace` | 1 | ENGINE-02 | T-04-INT | atomic finalize, no partial poisoning | unit | `pytest tests/test_downloader.py::test_atomic_finalize -x` | ❌ W0 | ⬜ pending |
| Disk pre-check: free < needed*margin → refuse | 1 | ENGINE-02 / D-05 | T-04-DISK | disk-exhaustion guard | unit (monkeypatch `shutil.disk_usage`) | `pytest tests/test_downloader.py::test_disk_precheck -x` | ❌ W0 | ⬜ pending |
| Real-network resumable download + md5 | 1 | ENGINE-02 | T-04-INT | HTTPS + TLS verify | integration (network) | `pytest tests/test_downloader_net.py -m network` | ❌ W0 (opt-in) | ⬜ pending |
| Cheap install-state probe + footprint, no SDK import | W0/1 | ENGINE-01 / D-11 | — | no heavy import | unit (tmp_path) | `pytest tests/test_install_state.py -x` | ❌ W0 | ⬜ pending |
| Import filename validation: reject `../`/absolute/non-`.onnx` | 1 | VOICE-04 / HARD-03 | T-04-PATH | path-traversal/zip-slip guard | unit | `pytest tests/test_voice_import.py::test_safe_dest -x` | ❌ W0 | ⬜ pending |
| Label override merge + tag search feeds filters | 1 | VOICE-06 / D-14 | T-04-REDOS | plain-substring match, no user regex | unit | `pytest tests/test_voice_labels.py -x` | ❌ W0 | ⬜ pending |
| Uninstall in-use block; else delete `.onnx`(+`.json`) | 1 | VOICE-07 / D-17 | T-04-FILE | delete only within cache dir | unit (tmp_path + in-mem db) | `pytest tests/test_uninstall.py -x` | ❌ W0 | ⬜ pending |
| Bulk partial cleanup globs `*.part` | 1 | VOICE-07 / D-18 | T-04-FILE | cache-scoped deletion | unit (tmp_path) | `pytest tests/test_uninstall.py::test_clean_partials -x` | ❌ W0 | ⬜ pending |
| Catalog filter/order reuse | 1 | D-03 | — | N/A | unit (existing) | `pytest tests/test_native_os_engine.py -x` | ✅ exists | ⬜ pending |
| Per-job voice selection persists | 1 | VOICE-05 | — | stale-id backstop (Phase-3 resolve) | unit/manual | (existing Upload picker path) | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_downloader.py` — resume offset, 206-vs-200 append/reset, md5 reject/accept, atomic finalize, disk precheck (ENGINE-02, D-05/06/07)
- [ ] `tests/test_downloader_net.py` — opt-in `@pytest.mark.network` real-HF resumable download (ENGINE-02)
- [ ] `tests/test_catalog.py` — manifest parse, curated subset, footprint/URL build, group-by-language (VOICE-01, D-01/03)
- [ ] `tests/test_install_state.py` — Piper/Kokoro cheap probe + footprint (ENGINE-01, D-11)
- [ ] `tests/test_voice_import.py` — filename/traversal validation + pair check + metadata read (VOICE-04, HARD-03)
- [ ] `tests/test_voice_labels.py` — override merge + tag search feeding filters (VOICE-06, D-14)
- [ ] `tests/test_uninstall.py` — in-use block (D-17), delete pair, bulk `.part` cleanup (VOICE-07, D-18)
- [ ] Register `network` marker in `pyproject.toml` (`markers = ["network: hits real endpoints"]`)
- [ ] `tests/fixtures/voices_manifest.json` — 2–3-entry excerpt (incl. a multi-speaker voice)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Background download with live byte progress, cancel, manual resume | ENGINE-04 / D-06/07/08 | Streamlit `st.fragment` polling UX; real network | Open Settings ▸ Voices, install a voice → progress advances; Cancel → stops, keeps `.part`; Resume → continues from offset, not restart |
| `file_uploader` `.onnx` + `.onnx.json` pair import | VOICE-04 | Streamlit upload widget + size cap | Import a downloaded Piper pair via upload AND via path entry → voice becomes selectable |
| Preview: cached sample (not installed) + live synth (installed) audibly play | VOICE-03 | Audio playback | Preview a catalog voice not installed (sample plays) and an installed one (live synth plays) |
| Settings `st.tabs` restructure; Voices tab is the hub | D-09 | Visual/layout | Settings renders tabs; Voices tab holds catalog + downloads + cross-engine browser + install/uninstall |
| Install-state + footprint badges render on Voices tab + Upload dropdown | ENGINE-03 / D-11 | Visual | Badges show "Ready" / "~X MB, downloads on first use" in both places without heavy import lag |
| Uninstall confirm + in-use block; bulk partial cleanup | VOICE-07 | Interactive confirm | Uninstall shows confirm + freed space; in-use voice is blocked; "Clean up partial downloads" clears orphans |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
