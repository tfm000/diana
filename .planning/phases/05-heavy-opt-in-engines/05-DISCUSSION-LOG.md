# Phase 5: Heavy Opt-In Engines - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-15
**Phase:** 5-heavy-opt-in-engines
**Areas discussed:** Build order & MVP slices, Heavy-install UX & footprint, License + GPU gates, F5 voice-cloning UX

---

## Build order & MVP slices

| Option | Description | Selected |
|--------|-------------|----------|
| Orpheus first | CPU-viable, broadest reach, lowest-risk proving slice | |
| F5-TTS first | Lead with the cloning showcase (heaviest upfront) | |
| All three in parallel | Concurrent slices; fastest if smooth, riskiest | |
| Other (free text) | — | ✓ |

**User's choice:** "all should be available as installs" — reframed away from picking a single first engine; the end state is all three installable.

| Option | Description | Selected |
|--------|-------------|----------|
| Fish S2 Pro is the slip | GPU-gated, narrowest audience — de-risks most | |
| F5-TTS is the slip | Defer cloning if torch proves hard | |
| None — all three must-have | Hold full scope, no fallback | ✓ |

**User's choice:** None — all three must-have.
**Notes:** No mandated first engine; planner sequences waves (recommended: shared install scaffold → per-engine vertical slices). Full scope held, no fallback slip.

---

## Heavy-install UX & footprint

| Option | Description | Selected |
|--------|-------------|----------|
| One 'Install' action | Single button handles deps + weights, combined status, no terminal | ✓ |
| Two explicit steps | 'Install runtime' then 'Download model' | |
| You decide | Claude's discretion | |

**User's choice:** One 'Install' action.

| Option | Description | Selected |
|--------|-------------|----------|
| Total + explicit confirm | Show full footprint + confirm | |
| Breakdown + confirm | Itemize deps vs model + disk check + confirm | ✓ |
| Warn-only, proceed | Caption only, no blocking | |

**User's choice:** Breakdown + confirm — **plus added requirement: "make sure the venv is used"** (heavy deps install into an isolated venv, not the global environment).

| Option | Description | Selected |
|--------|-------------|----------|
| No-terminal non-negotiable | Keep the locked constraint; in-app installer must do it all | ✓ |
| Documented command OK (heavy only) | Relax no-terminal for opt-in engines | |
| Decide after research | Defer feasibility | |

**User's choice:** No-terminal non-negotiable.
**Notes:** Combined with the venv requirement, this makes "provision + populate a venv and pip-install torch/llama-cpp from inside an eventually-frozen PyInstaller app, no terminal" the load-bearing technical risk → flagged for research (intersects Phase 6 / PKG-02).

---

## License + GPU gates

| Option | Description | Selected |
|--------|-------------|----------|
| Accept-once per engine | License shown + 'I accept' on first install; persisted | ✓ |
| Accept every download | Re-accept each install | |
| Inline notice, no accept click | Show license near Install, no explicit accept | |

**User's choice:** Accept-once per engine (blocking, persisted in app_settings).

| Option | Description | Selected |
|--------|-------------|----------|
| Decide after research | Confirm MPS support + VRAM floor first | ✓ |
| NVIDIA CUDA + VRAM only | Conservative; Macs hidden | |
| CUDA or Apple MPS | Also Apple Silicon if viable | |

**User's choice:** Decide after research (Fish "capable GPU" definition).

| Option | Description | Selected |
|--------|-------------|----------|
| Hidden entirely | Matches HEAVY-03 wording | |
| Shown but disabled + reason | Visible, greyed, with a "requires a capable GPU" note | ✓ |

**User's choice:** Shown but disabled + reason.
**Notes:** ⚠️ Refines HEAVY-03 + ROADMAP SC#3 ("hidden" → "shown-but-disabled-with-reason"). Reconciliation of REQUIREMENTS.md + ROADMAP wording flagged as an action so the verifier checks the intended behavior. User confirmed via deliberate selection from clear options.

---

## F5 voice-cloning UX

**Initial questions rejected** — user asked "why would the user add a reference clip?" Claude explained F5-TTS is a zero-shot voice-cloning model (no baked-in voices; it imitates a reference clip), then reframed the choice. User responded with a concrete vision (free text):

> "have a voice upload section that can be use for this and other potential future models. the user can supply the voice as an mp3 file + text file, or in app (i.e. the app can record the voice + notepad/text box to detail what was said)"

→ Captured as a reusable, engine-agnostic "Custom Voices" section (Settings ▸ Voices) with two input methods (upload mp3+txt; in-app record + typed transcript); transcript always user-provided (no STT dependency); clip validation + clear rejection.

| Option | Description | Selected |
|--------|-------------|----------|
| Saved & named | Custom voice reusable in picker + browser, removable | ✓ |
| Ephemeral per-job | Supply each time, nothing stored | |

**User's choice:** Saved & named.

| Option | Description | Selected |
|--------|-------------|----------|
| Bundle a default voice | F5 works out of the box; custom enhances | ✓ |
| No — user adds one first | F5 unusable until a clip is supplied | |

**User's choice:** Bundle a default voice (one license-clean default; "install → synthesize" satisfied).

---

## Claude's Discretion

- Orpheus voice model shape (mirror Kokoro single-model + named voices; default GGUF quantization; optional quant choice).
- Fish voice model (preset vs cloning) — resolve in research with the GPU gate.
- Exact venv mechanism, model repo IDs/revisions, inference signatures, wheel sources.
- Custom-voice metadata storage shape + bundled F5 default voice location.
- Clip-validation exact bounds; concurrent-install policy; install-phase progress reporting.

## Deferred Ideas

- Heavy-engine packaging/freezing, ffmpeg bundling, Windows CI → Phase 6 (venv-in-frozen-app researched in Phase 5).
- Production hardening → Phase 7.
- Auto-transcription of reference clips (local STT) — rejected this phase to avoid another heavy dependency.
- Reviewed-not-folded todos: `phase7-setup-scripts-per-user-paths.md`, `phase7-settings-env-var-key-exfiltration.md` (both Phase 7).
