# Phase 02 — Deferred Items

Out-of-scope discoveries logged during execution (per executor SCOPE BOUNDARY rule).
These are NOT fixed by Phase 02 plans.

## Pre-existing test failures (unrelated to plan files)

| Item | Detail | First seen | Status |
|------|--------|-----------|--------|
| `tests/test_llm_client_anthropic_cli.py::test_anthropic_cli_real_call` fails | Real end-to-end call via `claude-agent-sdk`; requires an active `claude login` session + Node.js Claude Code CLI. Not skipped via `importorskip` because the SDK *is* installed but the live session/CLI is unavailable in this environment. Fails identically on the clean baseline (commit 09c1a89, before any 02-01 edits) and touches no cleaner/registry/pipeline/summarizer code. | 02-01 Task 1 full-suite run | Deferred — environmental/live-call test, out of scope for the cleaner overhaul |
