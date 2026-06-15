# Phase 05 — Deferred Manual UAT

Manual user-acceptance verifications that could not be exercised interactively at a
checkpoint and are carried forward. Each item names what IS automated-test-covered vs
what still needs a human, and the exact steps to verify. This mirrors the Phase-3/4
deferred-UAT precedent: a deferred real-install verification is NOT a defect and NOT a
silent skip — the logic underneath is automated-tested with the subprocess/venv mocked.

---

## HEAVY-01 — Orpheus real install + by-ear synthesis (Plan 05-04)

- **Plan:** 05-04 (Orpheus vertical slice: install → select → synthesize)
- **Status:** DEFERRED — the real multi-GB install + by-ear synthesis was not exercised
  this session (NOT a defect, NOT a silent skip)
- **Deferred at:** 2026-06-15
- **Reason:** The verifying machine is a macOS dev box with no NVIDIA GPU where a
  multi-GB download + on-device synthesis is impractical to run in an automated `--auto`
  session. Per the Task-3 checkpoint authorization ("if a real install is not feasible on
  the verifying machine, write the steps into 05-HUMAN-UAT.md and resume — deferred UAT,
  not a defect"), the real install/synth steps are carried forward here.

### What IS verified (automated + agent pre-check)

- **Engine + worker logic** — `tests/test_orpheus_engine.py` (flipped skip→PASS):
  `OrpheusEngine.VOICES` is 8 `TTSVoice` enumerable with NO `orpheus_cpp` import;
  `initialize()` raises `FileNotFoundError` naming "Settings ▸ Voices" when uninstalled
  (D-16); `synthesize` shells `[<venv-python>, orpheus_worker.py]` with the chunk text as
  stdin JSON DATA (never a shell string — T-05-CMD), `HF_HOME` set in env, and round-trips
  the worker's WAV bytes (the subprocess is mocked — no real synth).
- **Registry wiring** — `tests/test_registry_heavy.py` (flipped skip→PASS): `orpheus` is in
  `list_engines()`, is UTF-8-capable (`_ASCII_ONLY_ENGINES["orpheus"] is False`), and the
  cheap enumeration/badge path imports no `torch`/`llama_cpp`/`orpheus_cpp`/`f5_tts`.
- **UI surfaces (interaction-level AppTest)** — `tests/test_orpheus_slice_apptest.py`
  (3 PASS): selecting uninstalled Orpheus on the Upload page surfaces the actionable
  "install … in Settings ▸ Voices" prompt and the exact `heavy_engine_failfast` gate wired
  into the Convert `disabled=` returns that message (and `None` for a light engine, so a
  light job is never gated); the Settings ▸ Voices "Heavy opt-in engines" Orpheus row
  renders with the itemized deps-vs-model footprint confirm + an Install action — with NO
  heavy SDK imported.
- **Two-phase install machinery** — `tests/test_heavy_install.py` (05-03, PASS): the
  `install_engine` two-phase deps→weights thread target with the `has_space` disk
  pre-check before any byte, the venv provisioner argv/order, and the `.{engine}.installed`
  marker — subprocess fully mocked.

### What is NOT verified (needs a human, on a machine where a multi-GB install is feasible)

Run these on a real install-capable machine (no terminal required for any step — that is
the point of HEAVY-01). Apple Silicon uses the abetlen `metal` wheel index; other
platforms use `cpu` (selected automatically by `orpheus_install_spec`).

1. **Install (two-phase progress).** Open **Settings ▸ Voices**, scroll to **Engine
   models ▸ Heavy opt-in engines ▸ Orpheus**. Confirm the row shows the itemized footprint
   (~deps MB + ~model MB ≈ total). Click **Install** once to confirm the footprint, then
   **Install** again. Watch the two-phase progress: first an "Installing dependencies… "
   step label (Phase A — `uv venv` + `uv pip install`, no byte bar), then a
   "Downloading model weights…" step (Phase B — GGUF + SNAC into the per-user HF cache).
   It should end at **"Ready · Orpheus installed"**. (Expect a multi-GB download; the GGUF
   is ~2.3 GB Q4_K_M plus the SNAC ONNX decoder.)
2. **Select + synthesize (by ear).** Go to **Upload**, select the **Orpheus** engine and a
   named voice (e.g. **Tara**). Upload a short `.txt` and click **Convert to Audio**.
   Confirm the job completes and the audio plays, and that it sounds like the Orpheus
   neural voice (by ear) — not silence, not a different engine.
3. **Default install untouched (D-02).** Confirm the lightweight default
   (native_os / Kokoro / Piper) still works exactly as before — selecting native_os or
   Kokoro and converting a short file is unchanged, and nothing heavy was pulled into the
   default path.
4. **(Optional) Uninstall reclaims space.** On the Orpheus row, click **Uninstall** →
   **Confirm uninstall**; it should report the freed MB and the row should return to the
   not-installed state. If a pending/in-progress job uses Orpheus, the uninstall must be
   refused with a "switch that job to another engine first" message (delete nothing).

### Resume signal

When a human has run steps 1–3 on an install-capable machine and confirms Orpheus
installs (no terminal) and synthesizes by ear with the default engines unchanged, this
item is satisfied. Until then it remains DEFERRED (carried, not failed).
