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

---

## HEAVY-02 — F5-TTS real install + accept-license + by-ear synthesis (Plan 05-05)

- **Plan:** 05-05 (F5 vertical slice: accept-license → install → select → synthesize with
  the bundled default voice)
- **Status:** DEFERRED — the real multi-GB torch install + by-ear synthesis was not
  exercised this session (NOT a defect, NOT a silent skip)
- **Deferred at:** 2026-06-15
- **Reason:** The verifying machine is a macOS dev box where a multi-GB `torch` +
  `F5TTS_v1_Base` download + on-device neural synthesis is impractical in an automated
  `--auto` session. Per the Task-3 checkpoint authorization ("if a real install is not
  feasible on the verifying machine, write the steps into 05-HUMAN-UAT.md and resume —
  deferred UAT, not a defect"), the real accept-license → install → synth steps are carried
  forward here. The bundled default voice itself was generated ON-DEVICE and IS produced
  this session (not deferred — see "What IS verified" below).

### What IS verified (automated + agent pre-check)

- **Engine + worker logic** — `tests/test_f5_engine.py` (flipped skip→PASS):
  `F5Engine.list_voices()` surfaces the bundled `f5_default` voice enumerable with NO
  `torch`/`f5_tts` import (D-17); `synthesize` shells `[<torch-venv-python>, f5_worker.py]`
  passing `ref_file`/`ref_text`/`gen_text` as stdin JSON DATA (never a shell string —
  T-05-CMD), `HF_HOME` set in env, and round-trips the worker's WAV bytes (the subprocess
  is mocked — no real torch synth). `initialize()` fail-fasts (D-16) when uninstalled.
- **License gate (round-trip)** — `tests/test_license_gate.py` (PASS): `accept_license` →
  `license_accepted` persists over a real temp SQLite DB, survives a re-read (fresh
  connection), is engine-scoped (accepting F5 does not accept Fish), and is idempotent
  (re-install never re-prompts — D-08).
- **UI surfaces (interaction-level AppTest)** — `tests/test_f5_slice_apptest.py` (4 PASS):
  (1) selecting uninstalled F5 on Upload surfaces the actionable "install … in Settings ▸
  Voices" prompt and `heavy_engine_failfast("f5")` drives the Convert `disabled=` (D-16);
  (2) the Settings ▸ Voices F5 row shows the CC-BY-NC non-commercial disclosure + the
  SWivid license link + "I accept" and NO Install control BEFORE acceptance (D-08); (3)
  once the accept-once flag is set in `app_settings`, the itemized deps-vs-model footprint
  confirm + Install appear and the accept gate is gone — all with NO `torch`/`f5_tts`
  imported.
- **Bundled default voice (D-15 / Q-E)** — generated on-device with macOS `say`
  (license-clean by construction): `diana/data/voices/f5_default.wav` (6.55 s, 22.05 kHz
  mono PCM_16, soundfile-readable) + `diana/data/voices/f5_default.txt` holding the EXACT
  transcript. `F5Engine._resolve_ref("f5_default")` resolves the clip via package
  resources and its `ref_text` matches the shipped `.txt` byte-for-byte.
- **Registry wiring** — `f5` is in `list_engines()`, routes to `F5Engine`, is UTF-8-capable
  (`_ASCII_ONLY_ENGINES["f5"] is False`), and the cheap enumeration/badge path imports no
  `torch`/`f5_tts` (verified by `sys.modules` assertion in the full suite).

### What is NOT verified (needs a human, on a machine where a multi-GB install is feasible)

Run these on a real install-capable machine (no terminal required for any step — that is
the point of HEAVY-02). F5 shares the `torch` venv (D-03): F5 installs torch, Fish reuses
it later.

1. **Accept the license (D-08).** Open **Settings ▸ Voices ▸ Engine models ▸ Heavy opt-in
   engines ▸ F5**. Confirm the row shows the **CC-BY-NC (non-commercial / personal use
   only)** disclosure + a **Read the license** link to `github.com/SWivid/F5-TTS`, and that
   **NO Install control is shown yet**. Click **I accept**. Confirm the footprint confirm +
   **Install** now appear. Re-open the row (or restart the app) and confirm the license is
   **NOT re-prompted** (accept-once persisted, D-08).
2. **Install (two-phase progress).** Click **Install** once to confirm the footprint
   (~deps GB + ~model GB), then **Install** again. Watch the two-phase progress: first an
   "Installing dependencies… " step label (Phase A — `uv venv` + `uv pip install f5-tts`,
   no byte bar), then a "Downloading model weights…" step (Phase B — the `F5TTS_v1_Base`
   checkpoint into the per-user HF cache). It should end at **"Ready · F5-TTS installed"**.
   (Expect a multi-GB download: torch + torchaudio + the F5 checkpoint.)
3. **Select + synthesize (by ear).** Go to **Upload**, select the **F5** engine and the
   **Default (F5)** voice. Upload a short `.txt` and click **Convert to Audio**. Confirm
   the job completes and the audio plays, that it is intelligible, and that it sounds like
   the bundled default reference voice (by ear) — not silence, not a different engine.
4. **Default install untouched (D-02).** Confirm the lightweight default
   (native_os / Kokoro / Piper) still works exactly as before — selecting native_os or
   Kokoro and converting a short file is unchanged, and nothing heavy was pulled into the
   default path.
5. **(Optional) Uninstall reclaims space (shared-torch rule).** On the F5 row, click
   **Uninstall** → **Confirm uninstall**; it should report the freed MB. If Fish is also
   installed (later), uninstalling F5 must keep the shared `torch` venv and only remove the
   `.f5.installed` marker; with nothing else using it, the venv tree is removed. If a
   pending/in-progress job uses F5, the uninstall must be refused with a "switch that job
   to another engine first" message (delete nothing).
6. **CONFIRM the bundled default clip's provenance (Q-E).** Listen to
   `diana/data/voices/f5_default.wav` and read `f5_default.txt`. The clip was self-generated
   on-device with macOS `say` (no third-party rights — license-clean). If you prefer, replace
   **both** `f5_default.wav` and `f5_default.txt` with a public-domain or self-recorded clip
   + its exact transcript (~6–12 s, mono). Confirm the provenance is acceptable for shipping.

### Resume signal

When a human has run steps 1–4 on an install-capable machine and confirms F5 installs
behind the accepted license (no terminal, no re-prompt), synthesizes the default voice by
ear, leaves the default engines unchanged, AND confirms the Q-E provenance (step 6), this
item is satisfied. Until then it remains DEFERRED (carried, not failed).
