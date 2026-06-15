# Phase 4: Engine Management & Voice Catalog - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-15
**Phase:** 4-Engine Management & Voice Catalog
**Areas discussed:** Catalog scope & layout, Download experience, Where the UI lives, Preview + custom labels, Uninstall/manage (added), Engine scope

---

## Catalog scope & layout

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid: curated + "Show all" | Curated best-per-language default + toggle to full manifest | ✓ |
| Curated subset only | Hand-picked subset; full manifest via manual import only | |
| Full manifest, filtered | Whole rhasspy manifest, tamed by Phase 3 filters | |

**User's choice:** Hybrid: curated + "Show all"

| Option | Description | Selected |
|--------|-------------|----------|
| Bundle a JSON snapshot | Ship manifest in-app; browse offline | |
| Fetch from HuggingFace at runtime | Pull live manifest on open | |
| Bundle + optional refresh | Ship snapshot + manual "Refresh catalog" | ✓ |

**User's choice:** Bundle + optional refresh

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse Phase 3 filters + search (flat) | Same filter widgets, flat list | |
| Grouped by language sections | Collapsible per-language sections | |
| Hybrid (recommended) | Reuse filters; flat when curated, grouped on "Show all" | ✓ |

**User's choice:** Hybrid layout (after asking how Phase 3 language filters relate to curation)
**Notes:** Clarified that curation = content (which voices listed) vs. Phase 3 language filter = a UI control narrowing whatever is displayed; same widgets reused, language options derived from the manifest rather than OS voices.

---

## Download experience

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm only above a size threshold | One-click small, confirm large | ✓ |
| Always confirm with size | Confirm every download | |
| One-click, no confirm | Immediate start | |

**User's choice:** Confirm above threshold — **plus** explicitly require a storage-space check on every download; raise an error badge and refuse if insufficient.

| Option | Description | Selected |
|--------|-------------|----------|
| Block + show needed vs free | Refuse, show numbers | ✓ |
| Warn but allow proceed | Warn, allow start | |

**User's choice:** Block + show needed vs free

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-resume on next attempt | Silent resume from .part | |
| Manual Resume button | Explicit resume control | ✓ |

**User's choice:** Manual Resume button

| Option | Description | Selected |
|--------|-------------|----------|
| Allow cancel, keep partial | Stop, retain .part for resume | ✓ |
| Allow cancel, discard partial | Stop, delete partial | |
| No cancel | Run to completion/failure | |

**User's choice:** Allow cancel, keep partial

---

## Where the UI lives

| Option | Description | Selected |
|--------|-------------|----------|
| New dedicated 'Voices' page | New numbered page as hub | |
| Fold into Settings | Sections in 5_Settings.py | |
| Expand the Upload page | Grow Upload picker area | |

**User's choice:** Break Settings into tabs/subpages with one dedicated to Voices (a variation on "fold into Settings").

| Option | Description | Selected |
|--------|-------------|----------|
| Unified list, filter by engine | All engines together + engine filter | ✓ |
| Per-engine sections/tabs | One section per engine | |

**User's choice:** Unified list, filter by engine

| Option | Description | Selected |
|--------|-------------|----------|
| Voices page + Upload dropdown | Badges in both places | ✓ |
| Only the Voices page | Management page only | |
| Only the Upload dropdown | Picker only | |

**User's choice:** Voices tab + Upload dropdown

---

## Uninstall / manage (added by user mid-discussion)

**User request:** "also allow the user to uninstall voices from the app, including partial files."

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm before deleting | Show freed space, confirm | ✓ |
| One-click remove | Immediate delete | |

**User's choice:** Confirm before deleting

| Option | Description | Selected |
|--------|-------------|----------|
| Allow, fall back to default | Remove + reset to default voice | |
| Block with a message | Refuse if in use, tell user to switch | ✓ |

**User's choice:** Block with a message

| Option | Description | Selected |
|--------|-------------|----------|
| Per-item + bulk cleanup | Row action + "clean all partials" | ✓ |
| Per-item only | Row action only | |
| Auto-clean on uninstall only | Only as part of uninstall | |

**User's choice:** Per-item + bulk cleanup
**Notes:** Flagged as an addition beyond the named ENGINE/VOICE requirements — needs a new requirement recorded in ROADMAP/REQUIREMENTS.

---

## Preview + custom labels

| Option | Description | Selected |
|--------|-------------|----------|
| Fetch sample on demand | Pull clip when Preview clicked | |
| Bundle curated samples + fetch rest | Ship curated samples, fetch others | ✓ |
| Fetch + cache | Fetch then cache in per-user dir | |

**User's choice:** Bundle curated samples + fetch rest (CONTEXT folds in caching from the third option as discretion).

| Option | Description | Selected |
|--------|-------------|----------|
| Upload both files in-app | file_uploader for .onnx + .json | ✓ |
| Point to a path on disk | Path entry import | ✓ |

**User's choice:** Allow BOTH. Plus the key reframing: "everything should work for ALL engines/voices, not just Piper."

| Option | Description | Selected |
|--------|-------------|----------|
| Override attributes + custom tags | Override prelabels + add tags | ✓ |
| Custom tags only | Tags only, prelabels read-only | |
| Rename + custom tags | Custom name + tags, attrs read-only | |

**User's choice:** Override attributes + custom tags

---

## Engine scope (clarification prompted by user's "all engines" note)

| Option | Description | Selected |
|--------|-------------|----------|
| Engine-agnostic UX, Piper+Kokoro downloads now | Generic layer; Piper catalog + Kokoro model; heavy engines Phase 5 | ✓ |
| Also build heavy-engine catalogs now | Pull Orpheus/F5/Fish into this phase | |
| Strict Piper-only this phase | Piper alone; Kokoro stays manual | |

**User's choice:** Engine-agnostic UX, Piper + Kokoro downloads now

---

## Claude's Discretion

- Download mechanism (streaming HTTP + Range for resumability, off the UI thread); the D-04 size-threshold value.
- Custom-label/tag + flag storage shape (candidate: `app_settings`); manifest JSON schema + bundled snapshot location; sample-cache layout.
- Concurrent-download policy; `.part` naming/locking.
- Install-state detection mechanism (filesystem probe vs. engine-reported) — must stay cheap (no heavy imports).
- Settings tab names/order; how Kokoro's single-model/many-voices shape maps onto the per-voice catalog UI.

## Deferred Ideas

- Heavy engines (Orpheus / F5-TTS / Fish) download + catalogs → Phase 5 (reuse this layer).
- Standalone dedicated voice-browser page (VNEXT-01) → future.
- Volume/pitch controls → not requested, out of scope.
- Reviewed todos `phase7-setup-scripts-per-user-paths.md` and `phase7-settings-env-var-key-exfiltration.md` → left in Phase 7.
