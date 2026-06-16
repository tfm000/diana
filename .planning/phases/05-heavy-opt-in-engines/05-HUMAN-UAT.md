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

---

## HEAVY-02 — Custom Voices cloning (real F5 clone by ear) (Plan 05-06)

- **Plan:** 05-06 (reusable engine-agnostic Custom Voices library + F5 cloning from a
  saved custom voice — D-11..D-14)
- **Status:** DEFERRED (real F5-clone synthesis ONLY) — the capture/upload, validation,
  save/name/remove, and picker/browser appearance ARE exercised this session; the actual
  by-ear F5 clone of a saved custom voice was not (NOT a defect, NOT a silent skip)
- **Deferred at:** 2026-06-15
- **Reason:** Cloning a saved custom voice runs the F5 model in the multi-GB `torch` venv,
  which is impractical to install + run in an automated `--auto` session on this macOS dev
  box (the same constraint as the 05-05 F5 install above). Per the Task-3 checkpoint
  authorization ("a real F5 clone is environment-dependent: if not feasible on the
  verifying machine, write the steps into 05-HUMAN-UAT.md and resume — deferred UAT, not a
  defect — the validation/save logic is automated-tested"), ONLY the real-clone step is
  carried forward; everything around it is verified below.

### What IS verified (automated + agent pre-check — no torch, fully exercised this session)

- **Custom Voices library logic** — `tests/test_custom_voices.py` (flipped skip→PASS, 10
  tests): `validate_clip` accepts a ~3 s **16 kHz** clip + transcript (sub-24 kHz OK,
  Pitfall 5/7), rejects an empty/whitespace transcript, a sub-1 s clip, and an
  unreadable/junk file — each returning a `(False, msg)` tuple and **NEVER raising**
  (the import-rejection discipline, D-13/T-05-VAL); `safe_custom_voice_dest` strips path
  components, enforces a `.wav`/`.mp3`/`.txt` allow-list, and raises `ValueError` on a
  traversal / disallowed extension (T-05-PATH); save→list→remove round-trips a named voice
  over a temp DB, and malformed `app_settings` metadata degrades to the id rather than
  crashing enumeration (T-05-LBLJSON).
- **Engine-agnostic storage (D-11)** — storage keys are `voice.custom.<id>` (NO engine
  segment) and `list_custom_voices()` takes no required engine arg — one shared pool that
  Fish reuses in 05-07. Verified by the key grep + the round-trip test.
- **Picker + cross-engine browser appearance (D-14)** — `tests/test_custom_voices_apptest.py`
  (3 PASS): a saved custom voice appears in `registry.get_engine_voices("f5")` (the Upload
  picker source) AND `registry.all_engine_voices()` (the **Browse all voices** cross-engine
  table source) alongside the bundled `f5_default`, and is removable — with NO
  `torch`/`f5_tts`/`torchaudio`/`vocos` imported on the enumeration path (ENGINE-01 / D-17).
- **UI surfaces (interaction-level AppTest)** — `tests/test_custom_voices_apptest.py`: the
  Settings ▸ Voices **Custom Voices** section renders BOTH input methods — an upload path
  (audio `file_uploader` + a transcript `text_area`/`.txt`) AND an in-app capture path
  (`st.audio_input` + a transcript `text_area`) — D-11; clip validation rejects an empty
  transcript and an unreadable clip with a clear message and never crashes the page (D-13).
- **F5 clone wiring (D-14, subprocess mocked)** — `F5Engine._resolve_ref(<custom-id>)`
  resolves a saved custom voice through `custom_voices.custom_voice_ref` to its
  `custom_voices_dir()/<id>.wav` clip + `<id>.txt` transcript, which `synthesize` then
  passes as stdin JSON DATA to the torch-venv worker (the existing T-05-CMD path from
  05-05). The handoff is verified by the 05-05 `tests/test_f5_engine.py` synth test; only
  the real torch inference is deferred here.

### What is NOT verified (needs a human, on a machine where the F5 torch venv is installed)

Run these on a real install-capable machine (no terminal required for any step — that is
the point of HEAVY-02). F5 must already be installed (see the 05-05 HEAVY-02 item above).

1. **Save a custom voice via in-app recording.** Open **Settings ▸ Voices ▸ Custom
   Voices ▸ Record a clip**. Use the in-app recorder to record a few seconds of clear
   speech, type the **exact** transcript of what you said, give the voice a name, and click
   **Add recorded voice**. Confirm a green success message, that the voice appears under
   **Your saved custom voices**, and that it also appears in the **Browse all voices** table
   above (tagged F5).
2. **Save a custom voice via upload + validation rejections.** On the **Upload a clip**
   tab, upload a short `.wav`/`.mp3` (about 2–12 s) + a transcript (typed or a `.txt`),
   name it, and click **Add custom voice** — confirm success. Then deliberately try a bad
   input (an empty transcript, or a sub-1 s clip) and confirm it is **rejected with a clear
   message and the page does not crash**.
3. **Clone by ear (the deferred core).** Go to **Upload**, select the **F5** engine and
   **your saved custom voice** (not the bundled default). Upload a short `.txt` and click
   **Convert to Audio**. Confirm the job completes and the audio **sounds like the cloned
   voice** (verified by ear) — recognizably your reference voice, not silence, not the
   bundled default, not a different engine.
4. **Reusable across jobs.** Convert a second short `.txt` with the same custom voice and
   confirm it is still selectable and clones consistently (the voice persists — D-14).
5. **Remove with in-use block + freed space.** In the Custom Voices library, click
   **Remove** on a voice that is NOT a current job's choice → **Confirm remove**; confirm it
   reports freed space and disappears from the library, the Upload picker, and the
   Browse-all table. Then confirm a voice that IS a pending/in-progress job's choice (or set
   as the F5 default) is **refused** with a "switch to another voice first" message
   (delete nothing).

### Resume signal

When a human has run steps 1–5 on an F5-installed machine and confirms a custom voice can
be captured (record + upload), validated (good accepted, bad rejected with a message),
cloned by ear, reused across jobs, and removed (with the in-use block honored), this item
is satisfied. Until then it remains DEFERRED (carried, not failed) — the surrounding
capture/validation/save/remove/enumeration logic is automated-test-covered above.

---

## HEAVY-03 — Fish S2 Pro real GPU install + by-ear synthesis (Plan 05-07)

- **Plan:** 05-07 (Fish vertical slice: GPU gate → accept-license → install → select →
  synthesize — the FINAL engine, completing the three-engine lineup D-01)
- **Status:** TESTABLE-HERE (EXPERIMENTAL) — superseded by quick-260616-hk6, which corrected
  D-09: fish-speech has **native MPS support** (PR #461, merged 2024-08-15), so Apple Silicon
  runs (slower than CUDA, unverified upstream → EXPERIMENTAL). The GPU gate is now TRI-STATE
  (`fish_capability` → {cuda, apple, none}). On THIS M5 Pro (48 GB unified) the gate resolves
  to tier **"apple"**, so the Fish row is **ENABLED-experimental behind the NC-license gate**
  here — the real Apple-Silicon MPS install + by-ear synthesis **CAN now be exercised on this
  box** (it was previously deferred as NVIDIA-only). The accept-once NC-license gate (D-08)
  and the D-16 Convert fail-fast remain fully verified by automated tests.
- **Updated at:** 2026-06-16 (quick-260616-hk6)
- **Reason it is now testable here:** the original deferral assumed Fish was effectively
  NVIDIA-CUDA-only (RESEARCH A5). That was false — fish-speech runs on Apple Silicon via
  Metal/MPS. The fast paths (`--compile`/Triton, the SGLang streaming engine) ARE CUDA-only
  and S2-Pro-on-MPS is unverified upstream, so Apple Silicon is offered as **EXPERIMENTAL**
  (runs, but may be slow/unstable). A real **NVIDIA ≥12 GB box remains the FULL-support
  path** (tier "cuda"); an under-spec/non-arm64 host stays tier "none" (shown-but-disabled
  with the honest NVIDIA-or-Apple reason). The MEDIUM-confidence fish-speech inference
  signature in `fish_worker.py` STILL needs confirming against the pinned commit at real
  install — that caveat is unchanged (it now applies equally to the MPS install here).

### What IS verified (automated + agent pre-check — the live no-GPU path, fully exercised)

- **Engine + worker logic** — `tests/test_fish_engine.py` (flipped skip→PASS):
  `FishEngine.list_voices()` surfaces the bundled `f5_default` voice (reused as Fish's
  zero-shot default — A6) enumerable with NO `torch`/`fish_speech` import (D-17);
  `synthesize` shells `[<torch-venv-python>, fish_worker.py]` passing
  `ref_file`/`ref_text`/`gen_text` as stdin JSON DATA (never a shell string — T-05-CMD),
  `HF_HOME` set in env, and round-trips the worker's WAV bytes (the subprocess is mocked —
  no real torch synth). `initialize()` refuses unless **BOTH** installed **AND** a capable
  GPU is present (D-10/D-16 — both the no-GPU and not-installed cases raise an actionable
  error).
- **GPU gate (D-09 corrected / D-10, torch-free, TRI-STATE)** — `tests/test_gpu_probe.py`
  (PASS): `capable_nvidia_gpu()` shells `nvidia-smi` only (the "cuda" probe), and
  `fish_capability()` shells `nvidia-smi` + `sysctl -n hw.memsize` to resolve
  {cuda, apple, none} with NO torch import on any branch. tier "cuda" (NVIDIA ≥12 GB) /
  tier "apple" (arm64 macOS ≥16 GB unified, EXPERIMENTAL via MPS) / tier "none" (honest dual
  NVIDIA-or-Apple reason). On THIS M5 Pro (48 GB unified, no `nvidia-smi`) it live-returns
  tier **"apple"** — Fish is enabled-experimental here.
- **UI surfaces (interaction-level AppTest)** — `tests/test_fish_slice_apptest.py` (6 PASS),
  exercising all three pinned tiers (the live box is tier "apple", so tiers are PINNED):
  (1) tier **"none"** -> the **Settings ▸ Voices Fish row is SHOWN with a DISABLED Install
  button + the honest NVIDIA-or-Apple reason caption** — NOT hidden, NO
  license/footprint/Install control (D-10);
  (2) tier **"apple"** -> the Fish row is **SHOWN and ENABLED-experimental**: the
  EXPERIMENTAL Metal/MPS caption is present and (license not yet accepted) the NC-license
  disclosure + "I accept" appears with NO disabled button;
  (3) selecting Fish on Upload (tier "none" pinned) surfaces the honest dual reason on the
  readiness note and `heavy_engine_failfast("fish")` drives the Convert `disabled=`
  (D-16/D-10);
  (4) tier **"cuda"** -> the Fish row shows the **Fish Audio Research License /
  CC-BY-NC-SA-4.0 non-commercial disclosure** + the `huggingface.co/fishaudio/s2-pro` link +
  "I accept" and **NO Install before acceptance** (D-08); (5) once accepted (persisted), the
  itemized deps-vs-model footprint confirm + Install appear and the accept gate is gone — all
  with NO `torch`/`fish_speech` imported on any path.
- **License gate (round-trip)** — `tests/test_license_gate.py` (PASS): the per-engine
  accept-once flag is engine-scoped (`license.accepted.fish` is independent of
  `license.accepted.f5`), persists over a real temp SQLite DB across a fresh connection, and
  is idempotent (re-install never re-prompts — D-08).
- **Registry wiring** — `fish` is in `list_engines()`, routes to `FishEngine`, is
  UTF-8-capable (`_ASCII_ONLY_ENGINES["fish"] is False`), and the cheap enumeration/badge
  path imports no `torch`/`fish_speech` (verified by `sys.modules` assertion in the full
  suite). The cross-engine browser lists Fish's voices even on a GPU-less box (browsing is
  GPU-independent; only install/use is gated).

### What is NOT verified (the EXPERIMENTAL Apple-Silicon MPS install — now testable HERE)

✅ **As of quick-260616-hk6 these steps CAN run on this M5 Pro** (tier "apple"): Fish is
enabled-experimental, so the real install + by-ear synthesis is exercisable on this Mac via
Metal/MPS — no NVIDIA box required for the experimental path. **Expectation:** it installs
and runs via MPS but **may be slow and/or unstable** (the fast CUDA paths are unavailable;
S2-Pro-on-MPS is unverified upstream). A real **NVIDIA ≥12 GB box remains the FULL-support
path** (tier "cuda") — run these there too to confirm the first-class experience. No terminal
is required for any step (the point of HEAVY-03). Fish shares the `torch` venv with F5 by
default (D-03 / Q-B); install F5 first if you want to confirm the shared-venv reuse.

1. **GPU gate OPENS on a capable machine (D-09 corrected / D-10).** Open **Settings ▸ Voices
   ▸ Engine models ▸ Heavy opt-in engines ▸ Fish**. On THIS M5 Pro confirm the row is
   **enabled** with an **EXPERIMENTAL — runs via Metal/MPS, slower than NVIDIA, unsupported
   upstream** caption (tier "apple"). On an NVIDIA box confirm it is enabled with **no**
   experimental caption (tier "cuda", full support). On an under-spec/non-arm64 host the row
   must remain SHOWN-but-DISABLED with the honest NVIDIA-or-Apple reason (tier "none") — that
   tier is automated-test-verified.
2. **Accept the NC license (D-08).** Confirm the Fish row shows the **Fish Audio Research
   License / CC-BY-NC-SA-4.0 (non-commercial / personal use only)** disclosure + a **Read the
   license** link to `huggingface.co/fishaudio/s2-pro`, and that **NO Install control is
   shown yet**. Click **I accept**. Confirm the footprint confirm + **Install** now appear.
   Restart the app and confirm the license is **NOT re-prompted** (accept-once persisted).
3. **Install (two-phase progress; CONFIRM the fish-speech inference signature, Q-D/A6).**
   Click **Install** to confirm the footprint, then **Install** again. Watch the two-phase
   progress: Phase A (`uv venv` + `uv pip install` the pinned
   `fish-speech @ git+…@e5e2926…`), then Phase B (the `fishaudio/s2-pro` weights into the
   per-user HF cache). It should end at **"Ready · Fish installed"**. **⚠️ At this point the
   MEDIUM-confidence fish-speech inference call in `diana/tts/heavy_workers/fish_worker.py`
   must be confirmed against the installed package** (the `TTSInferenceEngine` /
   `ServeTTSRequest` shape, decoder config/checkpoint filenames) — adjust that single
   function if the real API differs; the engine/JSON contract is fixed. **This caveat now
   applies equally to the MPS install on this box** (the worker selects `mps` +
   `PYTORCH_ENABLE_MPS_FALLBACK=1` when CUDA is absent). **Q-B fallback:** if installing
   fish-speech into the shared `torch` venv conflicts with F5's torch build, switch
   `fish_install_spec().venv_name` to a dedicated `"fish"` and update the
   `install_state._heavy_venv_name` mapping, then re-install.
4. **Select + synthesize (by ear).** Go to **Upload**, select the **Fish** engine and the
   **Default (Fish)** voice (or a saved custom voice). On this M5 Pro the readiness note
   should read **"Ready — … experimental on Apple Silicon (MPS) — may be slow."** Upload a
   short `.txt` and click **Convert to Audio**. Confirm the job completes, the audio plays,
   it is intelligible, and it sounds like the chosen reference voice (by ear) — not silence,
   not a different engine. **On MPS expect it to be slower** than an NVIDIA box; if it fails,
   capture the worker stderr (the inference-signature caveat in step 3 is the likely cause).
5. **Default + other engines untouched (D-02 / D-01).** Confirm the lightweight default
   (native_os / Kokoro / Piper) still works exactly as before, and that **Orpheus and F5
   still work** — the three-engine lineup (D-01) is complete and independent. Confirm no
   terminal was used for any install.
6. **(Optional) Uninstall reclaims space (shared-torch rule).** On the Fish row, click
   **Uninstall** → **Confirm uninstall**; it should report the freed MB. If F5 is also
   installed, uninstalling Fish must keep the shared `torch` venv and only remove the
   `.fish.installed` marker; with nothing else using it, the venv tree is removed. A
   pending/in-progress Fish job must refuse the uninstall ("switch that job first").

### Resume signal

When a human has run steps 1–5 — **on this M5 Pro via the EXPERIMENTAL MPS path (tier
"apple") and/or on an NVIDIA ≥12 GB box for the full-support path (tier "cuda")** — and
confirms Fish's GPU gate opens (with the experimental caption on Apple Silicon), the NC
license is accepted (no terminal, no re-prompt), the real fish-speech inference signature is
confirmed (step 3), Fish synthesizes the default/custom voice by ear, and the default +
Orpheus + F5 engines are unchanged, this item is satisfied. The **tri-state GPU gate
(shown-but-disabled tier "none" / enabled tier cuda+apple) is automated-test-verified**; only
the **real install + by-ear synth** (now exercisable here on MPS) awaits a human.
