# Phase 04 — Deferred Manual UAT

Manual user-acceptance verifications that could not be exercised interactively at a
checkpoint and are carried forward. Each item names what IS automated-test-covered vs
what still needs a human, and the exact steps to verify.

---

## VOICE-04 — Manual voice import (upload + path)

- **Plan:** 04-04 (full catalog browse + preview + manual import)
- **Status:** DEFERRED — interactive UX not human-verified (NOT a defect, NOT a silent skip)
- **Deferred at:** 2026-06-15
- **Reason:** No external Piper `.onnx` + `.onnx.json` pair was available on hand this
  session, so the import upload/path-entry steps (human-verify checkpoint steps 4-5)
  could not be exercised end-to-end.

### What IS verified (automated)

- The import **validation logic** is covered by passing unit tests:
  `tests/test_voice_import.py` (the Plan-01 HARD-03 traversal scaffold) flipped
  skip->pass when `safe_voice_dest` landed in 04-04 — it asserts the resolved dest stays
  contained under `model_dir()` and that a non-`.onnx`/`.onnx.json` extension, an absolute
  path, and `../` traversal all raise `ValueError`, while a plain pair is accepted.
- The UI wiring is present and the page parses clean: `5_Settings.py` contains the
  `st.file_uploader` + path-entry `text_input`, both routed through
  `catalog.safe_voice_dest`, with pair-completeness + `.onnx.json` JSON-parse checks.

### What is NOT verified (needs a human)

- The interactive upload/path-entry UX end-to-end: selecting a real Piper pair in the
  running app, seeing it validate, and confirming the imported voice becomes selectable
  for a job — plus the clear rejection messaging on a bad import (not a crash).

### To verify (when a Piper pair is available)

1. Launch `.venv/bin/python run.py`, open **Settings ▸ Voices**.
2. **Import from path** (sidesteps the upload size cap): point the path entry at any
   Piper `.onnx` with its sibling `.onnx.json` on disk -> confirm it imports and the voice
   becomes selectable on the **Upload** page (VOICE-04, with no engine edit).
3. **Import via upload:** use the file uploader to import the `.onnx` + `.onnx.json` pair
   -> confirm it validates and becomes selectable.
4. **Rejection paths:** try importing only one file of the pair, and a wrong file type
   (e.g. a `.txt`) -> confirm each shows a clear rejection message, not a crash.

### Closes

- VOICE-04 interactive acceptance (the logic is already proven by automated tests; this
  UAT confirms the Streamlit upload/path UX a unit test cannot reach).
