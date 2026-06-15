import asyncio
import json
import logging
import os
import threading
from importlib import resources
from pathlib import Path

import streamlit as st

from diana import paths
from diana.config import get_config, save_config
from diana.dashboard.sidebar import get_icon_image, setup_sidebar
from diana.dashboard.voice_cache import cached_all_engine_voices
from diana.dashboard.voice_cache import cached_voices as _cached_voices
from diana.dashboard.voice_cache import clear_voice_cache
from diana.database import get_setting, set_setting
from diana.downloads.downloader import clean_partials, download_file, has_space
from diana.tts import catalog, heavy_install, install_state
from diana.tts.kokoro_engine import (
    KOKORO_DEFAULT_VARIANT,
    KOKORO_MODEL_VARIANTS,
    kokoro_download_assets,
)
from diana.tts.orpheus_engine import orpheus_install_spec
from diana.tts.native_os_engine import (
    filter_voices,
    order_by_quality,
    resolve_selected_voice_id,
)
from diana.tts.registry import (
    create_engine,
    list_engines,
    resolve_default_voice,
)
from diana.tts.voice_labels import (
    apply_overrides,
    get_label_overrides,
    search_by_tag,
    set_label_overrides,
)
from diana.utils import detect_device_theme

logger = logging.getLogger(__name__)

# Short fixed text for the installed-voice live preview (D-12), mirroring the Upload
# page's DEFAULT_PREVIEW_TEXT so both pages sound the same.
_PREVIEW_TEXT = "Hello, this is a preview of my voice. Welcome to Diana."


@st.cache_data(show_spinner=False)
def _curated_piper_entries() -> dict:
    """Read the RAW bundled curated Piper snapshot ({voice_id: manifest entry}).

    ``catalog.load_bundled_manifest`` yields ``TTSVoice`` objects (for badges and
    the picker), but the walking-slice install needs each entry's raw ``files``
    map — the per-file repo path, ``size_bytes`` and ``md5_digest`` — to build the
    download URL and verify the bytes. Browsing stays offline (D-02): this only
    reads the bundled JSON shipped as package data, never the network.
    """
    raw = resources.files("diana.data").joinpath(
        "piper_voices_curated.json"
    ).read_text(encoding="utf-8")
    data = json.loads(raw)
    return data.get("voices", data) if isinstance(data, dict) else data


def _piper_install_targets(entry: dict) -> list[tuple[str, Path, str | None, int | None]]:
    """The (url, dest, md5, size) tuples to download for one Piper voice entry.

    Returns the ``.onnx`` and ``.onnx.json`` pair (the MODEL_CARD and anything else
    is excluded — only the model + its sibling config land on disk, mirroring
    ``catalog.voice_footprint_bytes``). Each ``files`` key is already the full
    repo-relative path, so the URL is just the HF resolve prefix + that path; the
    destination is ``model_dir()/{basename}`` where ``piper_engine._resolve_model_path``
    finds it (zero engine edit).
    """
    targets: list[tuple[str, Path, str | None, int | None]] = []
    for file_path, meta in entry.get("files", {}).items():
        if not (file_path.endswith(".onnx") or file_path.endswith(".onnx.json")):
            continue
        url = catalog.download_url(file_path)
        dest = paths.model_dir() / Path(file_path).name
        targets.append((url, dest, meta.get("md5_digest"), meta.get("size_bytes")))
    return targets


def _download_piper_voice(voice_id: str, entry: dict, state: dict) -> None:
    """Daemon-thread target: download a Piper voice's files, progress -> ``state``.

    CRITICAL (T-04-SRC / RESEARCH Anti-Patterns): this runs on a spawned thread and
    MUST NOT call ``st.*`` — a Streamlit command off the script thread leaks the
    ScriptRunContext and can crash the app. It writes ONLY to the shared ``state``
    dict; the ``@st.fragment`` poller renders everything from the script thread.

    Downloads the ``.onnx`` + ``.onnx.json`` in sequence (the config is tiny). The
    progress denominator is the manifest grand-total so the bar reflects the whole
    install, not just the current file (Pitfall 1 — never a zero Content-Length).
    A truthy ``state["cancel"]`` is forwarded to ``download_file``, which leaves the
    ``.part`` for Resume (D-06/D-07); on stopping, this thread sets the observable
    TERMINAL marker ``state["cancelled"] = True`` so the action column can switch the
    row from "Cancel" to "Resume" once the thread has actually exited (without it the
    record would read ``done=False, error=None`` forever and the row would stay stuck
    showing Cancel). Any exception lands in ``state["error"]``.
    """
    targets = _piper_install_targets(entry)
    grand_total = sum((size or 0) for _, _, _, size in targets) or state.get("total") or 1
    state["total"] = grand_total
    completed_bytes = 0
    try:
        for url, dest, md5, size in targets:
            base = completed_bytes

            def _progress(d: int, _t: int) -> None:
                state.update(downloaded=base + d, total=grand_total)

            download_file(
                url, dest, expected_md5=md5, expected_size=size,
                progress=_progress, cancel=lambda: state["cancel"],
            )
            if state["cancel"]:
                # D-07: stop here, .part kept for Resume (D-06). Mark a TERMINAL
                # cancelled state on the shared dict (NOT st.* — this is the worker
                # thread) so the script thread can render Resume once we have exited.
                state["cancelled"] = True
                return
            completed_bytes += (size or 0)
            state["downloaded"] = completed_bytes
        state["done"] = True
    except Exception as e:  # noqa: BLE001 — surface to the UI, NEVER st.* on this thread
        state["error"] = str(e)


def _new_dl_state(total: int) -> dict:
    """A fresh per-voice download-state record for ``st.session_state.dl_state``.

    ``cancel`` is the REQUEST flag the UI sets to ask the worker to stop; ``cancelled``
    is the TERMINAL marker the worker sets once it has actually stopped (so the action
    column can tell "Cancel pending" from "Cancelled — offer Resume"). A fresh record
    (e.g. one created by Resume) always starts with both False so the new attempt is
    genuinely in-flight again (D-06).
    """
    return {
        "downloaded": 0, "total": total, "done": False,
        "error": None, "cancel": False, "cancelled": False,
    }


def _download_action(state: dict | None) -> str:
    """Pure state -> action label for the Voices-tab action column (D-06/D-07).

    Mirrors the Phase-3 ``resolve_selected_voice_id`` precedent: a Streamlit-free,
    unit-testable decision so the cancel/resume transitions can be tested without a
    ScriptRunContext. Returns exactly one of:

      - ``"install"``    — no state yet, or a finished record was cleared: show Install.
      - ``"downloading"``— genuinely in-flight (not done/error, cancel not requested):
                           show Cancel.
      - ``"cancelling"`` — cancel was requested but the worker has not yet stopped
                           (``cancel`` True, ``cancelled``/``done``/``error`` not yet
                           set): show a disabled "Cancelling…" so a second writer
                           thread is NEVER spawned onto the same ``.part`` mid-stop
                           (Pitfall 3 / T-04-RETRIG).
      - ``"resume"``     — a TERMINAL interrupted record (``cancelled`` True) OR an
                           errored one: show Resume (offsets from the kept ``.part``).
      - ``"done"``       — the download finished: show Installed.

    Note ``done``/``error`` win over a lingering ``cancel`` request: an attempt that
    finished or failed before observing the cancel is reported as done/resume, not
    cancelling.
    """
    if not state:
        return "install"
    if state.get("done"):
        return "done"
    if state.get("error"):
        return "resume"
    if state.get("cancelled"):
        return "resume"
    if state.get("cancel"):
        return "cancelling"
    return "downloading"


def _can_spawn_download(state: dict | None) -> bool:
    """Pure spawn-guard: may a download thread be (re)spawned for this record?

    Pitfall 3 / T-04-RETRIG: block a respawn ONLY while a download is genuinely
    in-flight (the ``"downloading"`` action) or while a cancel is mid-flight but the
    worker has not yet exited (``"cancelling"``) — spawning then would put a second
    writer thread on the same ``.part``. Allow a (re)spawn when there is no record,
    when it finished/errored, or when it reached the TERMINAL cancelled state (Resume).
    Kept pure so the guard is unit-testable alongside ``_download_action``.
    """
    return _download_action(state) not in ("downloading", "cancelling")


@st.fragment(run_every="0.5s")
def _render_download_progress(voice_id: str) -> None:
    """Poll ``dl_state[voice_id]`` from the SCRIPT thread and draw progress (D-08).

    Runs as an ``st.fragment`` so it refreshes itself every 0.5s WITHOUT a full-page
    rerun — the page stays responsive while bytes stream (ENGINE-04). Every ``st.*``
    here executes on the script thread (safe); the download thread only mutates the
    shared dict this reads. Once ``done``/``error`` is set, the auto-refresh stops
    re-arming work because the next click rebuilds state.

    The Cancel/Resume action buttons live in the main script body (NOT in this
    fragment), so a terminal transition the worker writes between full reruns —
    ``error`` or the cancel-acknowledged ``cancelled`` marker — would not flip the
    row to "Resume" until some unrelated rerun. When this poll observes that the
    worker has just reached a terminal state, it requests a single FULL rerun
    (``st.rerun()``) so the action column re-renders Resume on its own; the 0.5s
    cadence keeps the page responsive (no busy-loop).

    The install-DONE transition is treated the same way (04-03 install->use fix): on
    the FIRST poll that sees ``done`` for this voice, the shared voice-enumeration
    cache is cleared (``clear_voice_cache``) and a single full ``st.rerun()`` fires so
    the just-installed voice appears in the Settings Default-Voice picker AND the
    Upload picker WITHOUT an app restart. The ``_dl_terminal_seen`` guard makes both
    the clear and the rerun happen exactly once per completed install, never on every
    0.5s poll. The cache clear runs HERE on the script thread — never on the download
    worker thread, which stays ``st.*``-free (T-04-SRC).
    """
    dl_state = st.session_state.get("dl_state", {})
    state = dl_state.get(voice_id)
    if not state:
        return
    if state["error"]:
        st.error(f"Download failed: {state['error']}")
    elif state["done"]:
        st.success("Installed.")
    elif state.get("cancelled"):
        st.warning("Cancelled. Resume to continue from where it stopped.")
    elif state["cancel"]:
        # Cancel requested; the worker is finishing its current write before it sets
        # the terminal ``cancelled`` marker. Show a transient note (no button here).
        st.caption("Cancelling…")
    elif state.get("phase") == "deps":
        # Phase A of a heavy-engine install (05-04): `uv venv` + `uv pip install` has no
        # clean byte totals, so the provisioner streams uv stdout LINES into
        # ``state["step"]`` instead of bytes. Render that step label rather than a byte
        # bar. Phase B (weights) and the Kokoro/Piper rows never set ``phase``, so they
        # keep the byte progress bar below (unchanged).
        st.caption(f"Installing dependencies… {state.get('step', '')}")
    else:
        total = state["total"] or 1
        if state.get("phase") == "weights" and not state.get("downloaded"):
            # Phase B just started (weights prefetch runs in a venv subprocess that does
            # not stream byte counts back here), so there is no denominator yet — show the
            # step label until the worker reports progress, never a 0/0 bar.
            st.caption(f"{state.get('step', 'Downloading model weights…')}")
        else:
            st.progress(
                min(state["downloaded"] / total, 1.0),
                text=f"{state['downloaded'] / 1e6:.1f} / {total / 1e6:.1f} MB",
            )

    # Trigger ONE full rerun when the worker has just reached a terminal state so the
    # main-body action column flips (errored/cancelled -> "Resume"; done -> the picker
    # refresh below) without needing an unrelated click. Guard with a per-voice flag so
    # we act exactly once per terminal transition (no rerun storm).
    _seen = st.session_state.setdefault("_dl_terminal_seen", set())
    _is_terminal = (
        bool(state["error"]) or bool(state.get("cancelled")) or bool(state["done"])
    )
    if _is_terminal and voice_id not in _seen:
        _seen.add(voice_id)
        # On a completed install, drop the shared voice cache so the new voice appears
        # in BOTH the Upload and Settings Default-Voice pickers on the next run without
        # an app restart (04-03 install->use fix). Errored/cancelled records leave the
        # cache untouched — nothing landed on disk to enumerate.
        if state["done"]:
            clear_voice_cache()
        st.rerun()
    elif not _is_terminal and voice_id in _seen:
        # A fresh attempt (Resume) reset the record — allow the next terminal rerun.
        _seen.discard(voice_id)


def _start_piper_download(voice_id: str, entry: dict, footprint: int) -> None:
    """Spawn the download thread for ``voice_id`` unless one is already in-flight.

    Pitfall 3 / T-04-RETRIG: a Streamlit rerun (or a double-click) must NOT spawn a
    second writer thread for the same voice — that would corrupt the shared ``.part``.
    Guard on the live ``dl_state`` record via the pure ``_can_spawn_download``: spawn
    only when none exists, the prior attempt finished/errored, or it reached the
    TERMINAL cancelled state (Resume). A merely "cancelling" record (cancel requested,
    worker not yet exited) is refused, so we never put a second writer on the same
    ``.part`` mid-stop. One in-flight download is serialized per voice id (RESEARCH
    Open Question 3).
    """
    if "dl_state" not in st.session_state:
        st.session_state.dl_state = {}
    existing = st.session_state.dl_state.get(voice_id)
    if not _can_spawn_download(existing):
        return  # genuinely in-flight or mid-cancel — do not double-spawn (Pitfall 3)
    state = _new_dl_state(footprint)
    st.session_state.dl_state[voice_id] = state
    threading.Thread(
        target=_download_piper_voice, args=(voice_id, entry, state), daemon=True
    ).start()


# The dl_state key for the engine-level Kokoro model download (D-19). Kokoro is ONE
# model with many baked-in voices, so it shares the Plan-03 dl_state/thread/fragment
# machinery under a single synthetic key rather than per-voice rows.
_KOKORO_DL_KEY = "__kokoro_model__"


def _kokoro_install_targets(variant: str) -> list[tuple[str, Path, int | None]]:
    """The (url, dest, size) tuples to download for one Kokoro install (D-19).

    Reuses ``kokoro_engine.kokoro_download_assets`` (the chosen model variant + the
    shared voices bin) and lands each into ``paths.model_dir()`` under its canonical
    filename — exactly where ``config.tts.kokoro.{model,voices}_path`` already point
    (config.py:32-33), so the engine finds them with zero edit. No md5 is verified for
    the GitHub-release assets (no published per-file digest); the disk-space pre-check,
    resumable ``.part`` and atomic ``os.replace`` from the generic layer still apply,
    and ``voices-v1.0.bin``'s size is the VERIFIED exact total (T-04-INT).
    """
    targets: list[tuple[str, Path, int | None]] = []
    for asset in kokoro_download_assets(variant):
        dest = paths.model_dir() / asset["filename"]
        targets.append((asset["url"], dest, asset.get("size_bytes")))
    return targets


def _download_kokoro_model(variant: str, state: dict) -> None:
    """Daemon-thread target: download the Kokoro model + voices, progress -> ``state``.

    The Kokoro analogue of ``_download_piper_voice`` (NOT a duplicate of the machinery
    — it reuses the same generic ``download_file``, the same shared ``state`` dict, and
    the same ``_download_action`` state model). CRITICAL (T-04-SRC): runs on a spawned
    thread and MUST NOT call ``st.*``; it writes ONLY the shared ``state`` dict, which
    the ``@st.fragment`` poller renders from the script thread. Downloads the variant
    ``.onnx`` then ``voices-v1.0.bin`` in sequence; the progress denominator is the
    grand-total of the two assets so the bar reflects the whole install. A truthy
    ``state["cancel"]`` is forwarded to ``download_file`` (leaving the ``.part`` for
    Resume — D-06/D-07) and then sets the TERMINAL ``cancelled`` marker so the action
    column can switch to Resume once the thread has exited. Any exception lands in
    ``state["error"]``.
    """
    targets = _kokoro_install_targets(variant)
    grand_total = sum((size or 0) for _, _, size in targets) or state.get("total") or 1
    state["total"] = grand_total
    completed_bytes = 0
    try:
        for url, dest, size in targets:
            base = completed_bytes

            def _progress(d: int, _t: int) -> None:
                state.update(downloaded=base + d, total=grand_total)

            download_file(
                url, dest, expected_size=size,
                progress=_progress, cancel=lambda: state["cancel"],
            )
            if state["cancel"]:
                state["cancelled"] = True  # D-07: .part kept for Resume (D-06)
                return
            completed_bytes += (size or 0)
            state["downloaded"] = completed_bytes
        state["done"] = True
    except Exception as e:  # noqa: BLE001 — surface to the UI, NEVER st.* on this thread
        state["error"] = str(e)


def _start_kokoro_download(variant: str, footprint: int) -> None:
    """Spawn the Kokoro download thread unless one is already in-flight (Pitfall 3).

    Mirrors ``_start_piper_download`` exactly, guarding the respawn through the shared
    pure ``_can_spawn_download`` so a rerun/double-click never puts a second writer on
    the same ``.part`` (T-04-RETRIG). One in-flight Kokoro download is serialized under
    ``_KOKORO_DL_KEY``.
    """
    if "dl_state" not in st.session_state:
        st.session_state.dl_state = {}
    existing = st.session_state.dl_state.get(_KOKORO_DL_KEY)
    if not _can_spawn_download(existing):
        return
    state = _new_dl_state(footprint)
    st.session_state.dl_state[_KOKORO_DL_KEY] = state
    threading.Thread(
        target=_download_kokoro_model, args=(variant, state), daemon=True
    ).start()


def _system_language_first(voices, system_lang):
    """Best-quality-first (D-09) with the system language's voices ahead (D-08)."""
    sys_lang = (system_lang or "").strip().lower()
    in_lang = [v for v in voices if (v.language or "").strip().lower() == sys_lang]
    others = [v for v in voices if (v.language or "").strip().lower() != sys_lang]
    return order_by_quality(in_lang) + order_by_quality(others)


def _catalog_raw_entries() -> dict:
    """RAW ``{voice_id: entry}`` for install — refreshed live (session) over bundled.

    D-01/D-02: browse starts from the bundled curated snapshot (offline). A "Refresh
    catalog" merges the live manifest's raw entries into session state so every
    browsed voice — not just the curated nine — can install (each entry carries the
    ``files`` path + ``size_bytes`` + ``md5`` the download needs). The bundled curated
    entries are always present as the base so curated voices install offline even
    before any refresh.
    """
    entries = dict(_curated_piper_entries())
    entries.update(st.session_state.get("catalog_entries_raw", {}))
    return entries


def _catalog_voices(show_all: bool) -> list:
    """The TTSVoice list to browse: curated-flat default, or the full set on show-all.

    Default (``show_all`` False): the curated best-per-language flat subset from the
    bundled snapshot (offline/instant, D-01). Show-all: the full manifest — the live
    refreshed list when a "Refresh catalog" has run this session, else the full
    bundled snapshot (D-02). Pure read of cached/bundled data; no network here (the
    only network touch is the explicit Refresh button).
    """
    if not show_all:
        return catalog.curated_subset(catalog.load_bundled_manifest())
    refreshed = st.session_state.get("catalog_voices_all")
    if refreshed is not None:
        return refreshed
    return catalog.load_bundled_manifest()


def _refresh_catalog_state() -> None:
    """Fetch the live manifest ONCE and cache both raw entries + parsed voices (D-02).

    The single network touch (``catalog.refresh_catalog_raw``), behind the explicit
    "Refresh catalog" button. Stores the raw entry map (for install of any voice) and
    the parsed ``TTSVoice`` list (for the show-all browse) in session state; a fetch
    failure degrades to the bundled snapshot inside ``refresh_catalog_raw`` and never
    crashes the page (Pitfall 6).
    """
    raw = catalog.refresh_catalog_raw()
    st.session_state["catalog_entries_raw"] = raw
    st.session_state["catalog_voices_all"] = catalog.parse_manifest(raw)


def _voice_dir_for_entry(entry: dict) -> str:
    """The voice's repo-relative dir (parent of its ``.onnx`` ``files`` key) for samples.

    Returns ``""`` when the entry has no ``.onnx`` file path (a degraded/empty entry),
    so the caller can skip the fetched-sample path gracefully.
    """
    for file_path in entry.get("files", {}):
        if file_path.endswith(".onnx"):
            return file_path.rsplit("/", 1)[0] if "/" in file_path else ""
    return ""


def _bundled_sample_path(voice_id: str) -> "Path | None":
    """A bundled curated preview clip for ``voice_id`` if one ships in-app (D-12).

    Looks for ``diana/data/samples/{voice_id}.mp3`` (the offline curated-sample home;
    the package-data glob ``data/samples/*`` was declared in Plan 02). Returns the
    path when present, else ``None`` (the caller then fetches+caches on demand).
    """
    try:
        res = resources.files("diana.data.samples").joinpath(f"{voice_id}.mp3")
        p = Path(str(res))
        return p if p.is_file() else None
    except (ModuleNotFoundError, FileNotFoundError):
        return None


def _preview_installed_voice(voice_id: str, speed: float) -> bytes:
    """Live-synthesize a short preview for an INSTALLED Piper voice (D-12/VOICE-03).

    Reuses the Phase-3 ``create_engine -> synthesize -> bytes`` path (1_Upload.py:234)
    on the piper engine. Cached in session by voice id so a repeat preview is instant.
    Runs on the script thread (Streamlit-safe); the heavy import lives in
    ``create_engine``.
    """
    cache_key = f"settings_preview_{voice_id}"
    cached = st.session_state.get(cache_key)
    if cached is not None:
        return cached
    eng = create_engine(config, engine_name="piper")
    audio = asyncio.run(eng.synthesize(_PREVIEW_TEXT, voice=voice_id, speed=speed))
    eng.shutdown()
    st.session_state[cache_key] = audio
    return audio


def _import_voice_pair(files) -> tuple[bool, str]:
    """Validate + land a manually uploaded ``.onnx`` + ``.onnx.json`` pair (D-13/VOICE-04).

    ``files`` is the ``st.file_uploader`` list. Validates EACH name through
    ``catalog.safe_voice_dest`` (basename + extension allow-list + resolved-prefix
    under ``model_dir`` — HARD-03/T-04-PATH), requires BOTH halves of the pair sharing
    one base (T-04-PAIR), confirms the ``.onnx.json`` parses as JSON, then writes both
    into ``paths.model_dir()`` where ``piper_engine._resolve_model_path`` finds them
    (zero engine edit). Returns ``(ok, message)``; never raises to the UI — a bad pair
    is reported, not crashed.
    """
    if not files:
        return False, "Select both the .onnx and its .onnx.json file."
    by_name = {f.name: f for f in files}
    onnx = [n for n in by_name if n.endswith(".onnx")]
    cfg = [n for n in by_name if n.endswith(".onnx.json")]
    if not onnx or not cfg:
        return False, (
            "Import needs BOTH files: the model `.onnx` and its `.onnx.json` config. "
            "If the .onnx is too large to upload, use 'Import from a path on disk' "
            "below (it sidesteps the upload size limit)."
        )
    # The pair must share one base (en_US-amy-medium.onnx + en_US-amy-medium.onnx.json).
    onnx_base = os.path.basename(onnx[0])[: -len(".onnx")]
    if not any(os.path.basename(c)[: -len(".onnx.json")] == onnx_base for c in cfg):
        return False, "The .onnx and .onnx.json names must match (same voice base)."
    try:
        dests: list[tuple[Path, bytes]] = []
        for name, f in by_name.items():
            if not (name.endswith(".onnx") or name.endswith(".onnx.json")):
                continue  # ignore any extra non-pair file the uploader returned
            dest = catalog.safe_voice_dest(name)  # raises on bad ext / traversal
            data = f.getvalue()
            if name.endswith(".onnx.json"):
                json.loads(data)  # T-04-PAIR: reject a corrupt/non-JSON config
            dests.append((dest, data))
        for dest, data in dests:
            dest.write_bytes(data)
    except ValueError as e:
        return False, str(e)
    except json.JSONDecodeError:
        return False, "The .onnx.json file is not valid JSON — re-download the pair."
    return True, f"Imported '{onnx_base}'. It is now selectable on the Upload page."


def _import_voice_from_path(onnx_path_str: str) -> tuple[bool, str]:
    """Import a Piper voice the user already has on disk, by path (D-13/VOICE-04).

    The path-entry half of the dual import — it sidesteps the ``file_uploader`` size
    cap (Pitfall 7) for large local ``.onnx`` files. Takes the ``.onnx`` path, locates
    the sibling ``.onnx.json``, validates BOTH basenames through
    ``catalog.safe_voice_dest`` (extension + containment), confirms the config parses,
    then copies both into ``paths.model_dir()``. Returns ``(ok, message)``; never
    raises to the UI.
    """
    raw = (onnx_path_str or "").strip().strip('"').strip("'")
    if not raw:
        return False, "Enter the full path to a .onnx file."
    src = Path(raw).expanduser()
    if not src.is_file():
        return False, f"File not found: {src}"
    if not src.name.endswith(".onnx"):
        return False, "Point to the model .onnx file (its .onnx.json sits beside it)."
    sibling = src.with_name(src.name + ".json")  # en_US-amy-medium.onnx.json
    if not sibling.is_file():
        return False, (
            f"Missing config file beside it: expected '{sibling.name}' next to the "
            ".onnx. Both files are required."
        )
    try:
        json.loads(sibling.read_bytes())  # T-04-PAIR
        onnx_dest = catalog.safe_voice_dest(src.name)         # raises on bad ext
        cfg_dest = catalog.safe_voice_dest(sibling.name)
        onnx_dest.write_bytes(src.read_bytes())
        cfg_dest.write_bytes(sibling.read_bytes())
    except ValueError as e:
        return False, str(e)
    except json.JSONDecodeError:
        return False, "The .onnx.json file is not valid JSON — check the file."
    return True, f"Imported '{src.name[:-len('.onnx')]}'. It is now selectable on Upload."


def _voice_partial_path(voice_id: str) -> Path:
    """The orphaned-download ``.part`` path for a Piper voice's ``.onnx`` (D-18).

    Pure path builder (Streamlit-free, unit-testable): ``model_dir()/{id}.onnx.part``
    — the exact name ``downloader.download_file`` writes while streaming the model. The
    per-item "Remove partial" action probes/unlinks this; scoped to ``model_dir()``
    (basename-joined, never a user path — T-04-FILE).
    """
    return paths.model_dir() / f"{voice_id}.onnx.part"


def _render_uninstall_control(voice_id: str, footprint: int) -> None:
    """Uninstall an installed Piper voice: in-use block -> confirm + freed space (D-16/D-17).

    Two-step, destructive-action UX (mirrors the warn/confirm idiom):

      1. The first "Uninstall" click runs ``install_state.voice_in_use`` FIRST. If it
         returns a reason (the voice is a non-terminal job's choice or the per-engine
         default — D-17), REFUSE with "This voice is {reason} — switch to another voice
         first" and delete nothing. Otherwise arm a per-voice confirm flag.
      2. With the flag armed, show the freed space (``footprint``) and a
         "Confirm uninstall" / "Cancel" pair. Confirm calls
         ``install_state.uninstall_piper_voice`` (deletes the ``.onnx`` + ``.onnx.json``
         within ``model_dir`` only — T-04-FILE), clears the shared voice cache so the
         voice disappears from every picker with NO restart (the 04-03 pattern), and
         reruns. Cancel disarms the flag.

    The confirm flag lives in ``st.session_state`` keyed per voice so two rows never
    interfere. Runs entirely on the script thread (Streamlit-safe).
    """
    _confirm_key = f"_uninstall_confirm_{voice_id}"
    if not st.session_state.get(_confirm_key):
        if st.button("Uninstall", key=f"uninstall_{voice_id}"):
            reason = install_state.voice_in_use(
                config.storage.database_path, "piper", voice_id
            )
            if reason:
                # D-17: block — tell the user to switch first, delete nothing.
                st.warning(
                    f"This voice is {reason} — switch to another voice first, "
                    "then uninstall it."
                )
            else:
                st.session_state[_confirm_key] = True
                st.rerun()
    else:
        # D-16: confirm step showing the freed space before deletion.
        st.caption(f"Uninstall frees ~{footprint / 1e6:.1f} MB. This cannot be undone.")
        _yes, _no = st.columns(2)
        with _yes:
            if st.button("Confirm uninstall", key=f"uninstall_yes_{voice_id}", type="primary"):
                freed = install_state.uninstall_piper_voice(voice_id)
                st.session_state.pop(_confirm_key, None)
                clear_voice_cache()  # voice leaves every picker with no restart (04-03)
                st.success(f"Uninstalled. Freed {freed / 1e6:.1f} MB.")
                st.rerun()
        with _no:
            if st.button("Cancel", key=f"uninstall_no_{voice_id}"):
                st.session_state.pop(_confirm_key, None)
                st.rerun()


def _render_kokoro_download_row() -> None:
    """Engine-level Kokoro "model installed?" row with the in-UI download (D-19/D-04).

    Kokoro is ONE model with many baked-in voices (D-19/discretion), so this is a
    single engine-level row — NOT per-voice rows. When installed it shows a Ready
    badge. When not, it offers a variant picker (default ``int8`` ~88 MB) and a
    Download model action that runs the SAME generic flow as Piper: the universal
    ``has_space`` disk pre-check (D-05), then the threaded ``download_file`` (the
    Plan-03 ``dl_state``/``st.fragment`` machinery, reused verbatim under
    ``_KOKORO_DL_KEY`` — no duplicated thread/poll code) for the chosen ``.onnx`` +
    ``voices-v1.0.bin`` into ``model_dir()``. Because the f32 asset (~310 MB) crosses
    the D-04 >200 MB threshold, a footprint confirm is shown before a large download
    starts. On completion the model flips to Ready and Kokoro is usable with zero
    further setup (the wget hint is gone). Cancel/Resume work exactly as for Piper.
    """
    installed = install_state.kokoro_model_installed()
    with st.container(border=True):
        info_col, action_col = st.columns([3, 1])
        with info_col:
            st.markdown("**Kokoro** — one model, many built-in voices")
            if installed:
                st.success("Ready · Kokoro model installed", icon="✅")
            else:
                st.caption("Model not installed — download it once to use Kokoro voices.")

        dl_state = st.session_state.get("dl_state", {})
        state = dl_state.get(_KOKORO_DL_KEY)
        action = _download_action(state)
        active = bool(state) and action != "install"

        with action_col:
            if installed and action in ("install", "done"):
                st.button("Installed", key="kokoro_installed", disabled=True)
            elif action == "downloading":
                if st.button("Cancel", key="kokoro_cancel"):  # D-07
                    state["cancel"] = True
                    st.rerun()
            elif action == "cancelling":
                st.button("Cancelling…", key="kokoro_cancelling", disabled=True)
            elif action == "resume":
                if st.button("Resume", key="kokoro_resume"):  # D-06: offsets from .part
                    _variant = st.session_state.get("_kokoro_variant", KOKORO_DEFAULT_VARIANT)
                    _size = int(KOKORO_MODEL_VARIANTS[_variant]["size_bytes"]) + 28_214_398
                    _start_kokoro_download(_variant, _size)
                    st.rerun()

        # Live byte-progress / result, polled from the script thread (D-08), reusing
        # the SAME fragment as Piper (keyed by the synthetic Kokoro id).
        if active:
            _render_download_progress(_KOKORO_DL_KEY)

        # Variant picker + Download action when not installed and not already running.
        if not installed and not active:
            _variant = st.selectbox(
                "Model variant",
                list(KOKORO_MODEL_VARIANTS.keys()),
                index=list(KOKORO_MODEL_VARIANTS.keys()).index(KOKORO_DEFAULT_VARIANT),
                format_func=lambda k: KOKORO_MODEL_VARIANTS[k]["label"],
                key="_kokoro_variant",
            )
            # Grand total = chosen model + the shared voices bin (exact 28,214,398).
            _footprint = int(KOKORO_MODEL_VARIANTS[_variant]["size_bytes"]) + 28_214_398
            _big = _footprint > 200_000_000  # D-04 >200 MB confirm threshold
            _confirm_key = "_kokoro_dl_confirm"

            if _big and not st.session_state.get(_confirm_key):
                # D-04: explicit footprint confirm BEFORE a large download starts.
                st.warning(
                    f"This download is large (~{_footprint / 1e6:.0f} MB). "
                    "It will be saved to your per-user model cache."
                )
                if st.button("Download model", key="kokoro_download_confirm", type="primary"):
                    st.session_state[_confirm_key] = True
                    st.rerun()
            else:
                if st.button("Download model", key="kokoro_download", type="primary"):
                    st.session_state.pop(_confirm_key, None)
                    # D-05: universal disk-space pre-check gates the download.
                    ok, free = has_space(paths.model_dir(), _footprint)
                    if not ok:
                        st.error(
                            f"Not enough disk space: need ~{_footprint / 1e6:.0f} MB "
                            f"(plus headroom), only {free / 1e6:.0f} MB free. "
                            "Free up space and try again."
                        )
                    else:
                        _start_kokoro_download(_variant, _footprint)
                        st.rerun()


def _start_heavy_install(engine: str, spec, footprint: int) -> None:
    """Spawn the heavy-engine install thread unless one is already in-flight (Pitfall 3).

    The heavy-engine analogue of ``_start_kokoro_download``: it guards the respawn
    through the shared pure ``_can_spawn_download`` (so a rerun/double-click never puts a
    second installer on the same venv — T-04-RETRIG) and runs
    ``heavy_install.install_engine`` (the 05-03 two-phase deps->weights thread target) on
    a daemon thread that writes ONLY the shared ``state`` dict (T-05-SRC). One in-flight
    install per engine is serialized under ``f"__{engine}_install__"``.
    """
    key = f"__{engine}_install__"
    if "dl_state" not in st.session_state:
        st.session_state.dl_state = {}
    existing = st.session_state.dl_state.get(key)
    if not _can_spawn_download(existing):
        return
    state = _new_dl_state(footprint)
    st.session_state.dl_state[key] = state
    threading.Thread(
        target=heavy_install.install_engine, args=(spec, state), daemon=True
    ).start()


def _engine_in_use_reason(engine: str) -> str | None:
    """Human reason a heavy engine may NOT be uninstalled, else ``None`` (D-16/D-17).

    The engine-level analogue of ``install_state.voice_in_use``: refuse to remove an
    engine that a NON-TERMINAL (pending/in-flight) job still needs, and say so, so the
    worker never reaches a job whose engine was deleted mid-flight. A terminal job's
    engine (a finished/failed conversion) does NOT block — its audio already exists.
    Cheap DB read only (NO engine SDK import — ENGINE-01); ``database``/``models`` are
    imported lazily.
    """
    from diana.database import list_jobs
    from diana.models import JobStatus

    terminal = {JobStatus.COMPLETED, JobStatus.FAILED}
    for job in list_jobs(config.storage.database_path):
        if job.tts_engine == engine and job.status not in terminal:
            return "in use by a pending or in-progress job"
    return None


def _render_heavy_uninstall_control(engine: str, footprint: int) -> None:
    """Two-step uninstall for an installed heavy engine: in-use block -> confirm + freed.

    Mirrors ``_render_uninstall_control`` (the Piper-voice destructive-action UX) but at
    the ENGINE level: the first click runs ``_engine_in_use_reason`` and REFUSES (delete
    nothing) when a non-terminal job still needs the engine; otherwise it arms a confirm
    flag, then a "Confirm uninstall"/"Cancel" pair calls
    ``install_state.uninstall_heavy_engine`` (removes the marker + the per-engine venv
    tree, scoped to ``venvs_dir()`` — T-05-EXE; shared-torch engines keep the tree until
    the last one goes). The freed bytes are shown; the cross-engine cache is cleared so
    the engine's Ready state flips everywhere with no restart. Script-thread only.
    """
    _confirm_key = f"_heavy_uninstall_confirm_{engine}"
    if not st.session_state.get(_confirm_key):
        if st.button("Uninstall", key=f"heavy_uninstall_{engine}"):
            reason = _engine_in_use_reason(engine)
            if reason:
                st.warning(
                    f"{engine.capitalize()} is {reason} — switch that job to another "
                    "engine first, then uninstall."
                )
            else:
                st.session_state[_confirm_key] = True
                st.rerun()
    else:
        st.caption(
            f"Uninstall frees ~{footprint / 1e6:.0f} MB. This cannot be undone."
        )
        _yes, _no = st.columns(2)
        with _yes:
            if st.button("Confirm uninstall", key=f"heavy_uninstall_yes_{engine}",
                         type="primary"):
                freed = install_state.uninstall_heavy_engine(engine)
                st.session_state.pop(_confirm_key, None)
                clear_voice_cache()
                st.success(f"Uninstalled {engine.capitalize()}. "
                           f"Freed {freed / 1e6:.0f} MB.")
                st.rerun()
        with _no:
            if st.button("Cancel", key=f"heavy_uninstall_no_{engine}"):
                st.session_state.pop(_confirm_key, None)
                st.rerun()


def _render_heavy_engine_row(engine: str, spec) -> None:
    """A heavy opt-in engine install row: footprint confirm + disk pre-check + 2-phase.

    The generic heavy-engine row F5/Fish reuse (this slice wires Orpheus). Built on the
    Kokoro-row machinery (``_download_action`` state model, ``_can_spawn_download`` guard,
    the ``@st.fragment`` progress poller) but swapping the download substrate for the
    05-03 provisioner:

      * D-04 ITEMIZED footprint confirm BEFORE any byte — heavy installs always exceed
        the >200 MB threshold, so the confirm always shows, itemizing deps vs model from
        ``spec.deps_bytes`` / ``spec.weights_bytes``.
      * D-05 disk pre-check on Install: ``has_space(venvs_dir(), deps + weights)`` refuses
        with a clear "need X / only Y free" message before spawning.
      * the two-phase install runs on a daemon thread (``_start_heavy_install`` ->
        ``heavy_install.install_engine``); ``_render_download_progress`` shows the Phase-A
        step label then the Phase-B weights step (the ``phase``/``step`` extension above).
      * when installed, a Ready badge + the two-step engine uninstall control.

    Cheap by design: a filesystem install probe + a static spec — NO heavy SDK import.
    """
    installed = install_state.heavy_engine_installed(engine)
    key = f"__{engine}_install__"
    label = engine.capitalize()
    deps_mb = spec.deps_bytes / 1e6
    model_mb = spec.weights_bytes / 1e6
    total_bytes = spec.deps_bytes + spec.weights_bytes
    total_mb = total_bytes / 1e6

    with st.container(border=True):
        info_col, action_col = st.columns([3, 1])
        with info_col:
            st.markdown(f"**{label}** — neural voices, runs on-device (opt-in)")
            if installed:
                st.success(f"Ready · {label} installed", icon="✅")
            else:
                st.caption(
                    "Not installed — a one-time download sets up an isolated "
                    "environment plus the voice model."
                )

        dl_state = st.session_state.get("dl_state", {})
        state = dl_state.get(key)
        action = _download_action(state)
        active = bool(state) and action != "install"

        with action_col:
            if installed and action in ("install", "done"):
                _render_heavy_uninstall_control(
                    engine, install_state.heavy_footprint_bytes(engine)
                )
            elif action == "downloading":
                if st.button("Cancel", key=f"{engine}_cancel"):  # D-07
                    state["cancel"] = True
                    st.rerun()
            elif action == "cancelling":
                st.button("Cancelling…", key=f"{engine}_cancelling", disabled=True)
            elif action == "resume":
                if st.button("Resume", key=f"{engine}_resume"):
                    _start_heavy_install(engine, spec, total_bytes)
                    st.rerun()

        # Live two-phase progress (deps step label -> weights), polled from the script
        # thread, reusing the SAME fragment as Kokoro/Piper (keyed by the install key).
        if active:
            _render_download_progress(key)

        # Itemized footprint confirm + disk pre-check + Install, when not installed and
        # not already running.
        if not installed and not active:
            st.caption(
                f"{label} needs ~{deps_mb:.0f} MB dependencies + ~{model_mb:.0f} MB "
                f"model (~{total_mb:.0f} MB total). Saved to your per-user cache."
            )
            _confirm_key = f"_{engine}_install_confirm"
            # D-04: heavy installs ALWAYS exceed >200 MB, so always require a confirm.
            if not st.session_state.get(_confirm_key):
                if st.button("Install", key=f"{engine}_install_confirm", type="primary"):
                    st.session_state[_confirm_key] = True
                    st.rerun()
            else:
                if st.button("Install", key=f"{engine}_install", type="primary"):
                    st.session_state.pop(_confirm_key, None)
                    # D-05: disk pre-check against venvs_dir() before any byte.
                    ok, free = has_space(paths.venvs_dir(), total_bytes)
                    if not ok:
                        st.error(
                            f"Not enough disk space: need ~{total_mb:.0f} MB "
                            f"(plus headroom), only {free / 1e6:.0f} MB free. "
                            "Free up space and try again."
                        )
                    else:
                        _start_heavy_install(engine, spec, total_bytes)
                        st.rerun()


def _render_voice_row(voice, entry: dict, speed: float) -> None:
    """One catalog row: badge + install/resume/cancel + preview (D-11/D-06/D-12).

    Shared by the curated flat view and the grouped show-all view so both render
    identically. ``entry`` is the raw manifest entry for this voice (``files`` map);
    an empty entry (a refreshed voice whose raw entry is unavailable) disables Install
    with a "Refresh catalog" nudge rather than spawning a no-op download. Preview is
    three-mode (D-12/VOICE-03): live synthesis when installed, a bundled clip when one
    ships, else an on-demand fetched+cached ``speaker_0.mp3``.
    """
    installed = install_state.piper_voice_installed(voice.id)
    has_entry = bool(entry.get("files"))
    # Footprint: on-disk size when installed, else the manifest estimate (D-11).
    footprint = (
        install_state.piper_footprint_bytes(voice.id)
        if installed
        else catalog.voice_footprint_bytes(entry)
    )
    mb = footprint / 1e6

    with st.container(border=True):
        info_col, action_col = st.columns([3, 1])
        with info_col:
            st.markdown(f"**{voice.name}**  \n`{voice.id}` · {voice.language} · {voice.tier}")
            # ENGINE-03 / D-11 install-state + footprint badge.
            if installed:
                st.success(f"Ready · {mb:.1f} MB on disk", icon="✅")
            elif has_entry:
                st.caption(f"~{mb:.1f} MB, downloads on first use")
            else:
                st.caption("Size unknown — click **Refresh catalog** to enable install")

        dl_state = st.session_state.get("dl_state", {})
        state = dl_state.get(voice.id)
        action = _download_action(state)  # pure state -> action (D-06/D-07)
        active = bool(state) and action != "install"

        with action_col:
            if installed and action in ("install", "done"):
                st.button("Installed", key=f"installed_{voice.id}", disabled=True)
                _render_uninstall_control(voice.id, footprint)
            elif action == "downloading":
                if st.button("Cancel", key=f"cancel_{voice.id}"):  # D-07
                    state["cancel"] = True
                    st.rerun()
            elif action == "cancelling":
                # Cancel requested, worker not yet stopped — never offer Resume here
                # (a second writer on the same .part — Pitfall 3).
                st.button("Cancelling…", key=f"cancelling_{voice.id}", disabled=True)
            elif action == "resume":
                # D-06: Resume re-spawns, offsetting from the existing .part.
                if st.button("Resume", key=f"resume_{voice.id}"):
                    _start_piper_download(voice.id, entry, int(footprint))
                    st.rerun()
            elif not has_entry:
                # No raw entry yet (a refreshed voice we lack files for) — cannot build
                # a download URL, so disable Install rather than spawn a no-op thread.
                st.button("Install", key=f"install_{voice.id}", type="primary", disabled=True)
            else:
                if st.button("Install", key=f"install_{voice.id}", type="primary"):
                    # D-05: universal disk-space pre-check gates EVERY download.
                    ok, free = has_space(paths.model_dir(), int(footprint))
                    if not ok:
                        st.error(
                            f"Not enough disk space: need ~{footprint / 1e6:.1f} MB "
                            f"(plus headroom), only {free / 1e6:.1f} MB free. "
                            "Free up space and try again."
                        )
                    else:
                        _start_piper_download(voice.id, entry, int(footprint))
                        st.rerun()

        # Live byte-progress / result, polled from the script thread (D-08).
        if active:
            _render_download_progress(voice.id)

        # PARTIAL CLEANUP (D-18) — per item. An interrupted download leaves a
        # ``{voice}.onnx.part``; offer a one-click "Remove partial" to clear just this
        # one (the bulk action lives below the catalog). Show it whenever a partial is
        # actually present AND no writer thread is genuinely live — i.e. in the
        # cancelled/resume state (where the row ALSO offers Resume above), the errored
        # state, and the orphan (no ``dl_state`` record) case. NEVER while a download is
        # "downloading"/"cancelling": deleting a ``.part`` under an active write would
        # corrupt it (Pitfall 3 — keep that guard). ``action`` is the single source of
        # truth here; an orphan ``.part`` with no record yields ``action == "install"``,
        # which is (correctly) not blocked.
        if action not in ("downloading", "cancelling") and _voice_partial_path(voice.id).exists():
            if st.button("Remove partial", key=f"rmpart_{voice.id}"):
                _voice_partial_path(voice.id).unlink(missing_ok=True)
                # Clear the in-session record so the row resets to Install rather than
                # staying stuck on Resume for a now-deleted partial (the dl_state is the
                # action source; a stale cancelled record would otherwise keep "Resume").
                st.session_state.get("dl_state", {}).pop(voice.id, None)
                st.rerun()

        # PREVIEW (D-12/VOICE-03): live synth when installed; a bundled or on-demand
        # fetched+cached sample clip when not. Plays via st.audio on the script thread.
        if st.button("Preview", key=f"preview_{voice.id}"):
            if installed:
                try:
                    with st.spinner("Synthesizing preview…"):
                        st.audio(_preview_installed_voice(voice.id, speed), format="audio/wav")
                except Exception as e:  # noqa: BLE001 — surface, never crash the tab
                    st.error(f"Preview failed: {e}")
            else:
                bundled = _bundled_sample_path(voice.id)
                if bundled is not None:
                    st.audio(str(bundled), format="audio/mp3")  # offline curated clip
                else:
                    voice_dir = _voice_dir_for_entry(entry)
                    if not voice_dir:
                        st.info("Preview unavailable — click **Refresh catalog**, then retry.")
                    else:
                        try:
                            with st.spinner("Fetching sample…"):
                                clip = catalog.fetch_sample(voice_dir)  # cached after first
                            st.audio(str(clip), format="audio/mp3")
                        except Exception as e:  # noqa: BLE001 — Pitfall 6 graceful 404
                            st.warning(
                                "Couldn't fetch a sample for this voice "
                                f"({e}). It may have moved — try **Refresh catalog**."
                            )


def _cross_engine_badge(engine: str, voice) -> None:
    """Render the install-state/footprint badge for one cross-engine browser row (D-11).

    Cheap detection only (``install_state`` filesystem probe — NO engine SDK import,
    ENGINE-01): native_os voices are OS-provided so they are always "Ready" (and are
    browse/preview/label-only — nothing to download or uninstall); a Piper voice shows
    its on-disk footprint when installed, else the manifest estimate with a "downloads
    on first use" note; Kokoro is one model with baked-in voices (D-19), so every
    Kokoro voice reflects the single engine-level "model installed?" probe.
    """
    if engine == "native_os":
        st.caption("OS voice · always Ready · browse / preview / label only")
        return
    if engine == "piper":
        if install_state.piper_voice_installed(voice.id):
            mb = install_state.piper_footprint_bytes(voice.id) / 1e6
            st.success(f"Ready · {mb:.1f} MB on disk", icon="✅")
        else:
            est = catalog.voice_footprint_bytes(_catalog_raw_entries().get(voice.id, {}))
            if est:
                st.caption(f"~{est / 1e6:.1f} MB, downloads on first use")
            else:
                st.caption("Not installed — install it from the Piper catalog below")
        return
    if engine == "kokoro":
        if install_state.kokoro_model_installed():
            st.success("Ready · Kokoro model installed", icon="✅")
        else:
            st.caption("Kokoro model not installed — downloads on first use")
        return
    if engine == "orpheus":
        # Heavy opt-in engine (HEAVY-01): cheap filesystem probe of the per-engine venv
        # + marker — NO orpheus_cpp/llama_cpp import on the badge path (ENGINE-01/D-17).
        if install_state.heavy_engine_installed("orpheus"):
            st.success("Ready · Orpheus installed", icon="✅")
        else:
            st.caption("~2.3 GB+, downloads on install — set up in Engine models above")
        return
    st.caption("")  # unknown engine — no badge


def _parse_tags(raw: str) -> list[str]:
    """Split a comma-separated tags input into a clean, de-duplicated list (D-14).

    Trims whitespace, drops empties, and de-dupes while preserving order. Plain text
    only — these feed the substring tag search, never a regex (T-04-REDOS).
    """
    out: list[str] = []
    seen: set[str] = set()
    for part in (raw or "").split(","):
        tag = part.strip()
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out


def paginate(items, page: int, page_size: int):
    """Slice ``items`` into one page — the pure, Streamlit-free pagination core.

    The cross-engine browser filters the FULL merged voice list first, then hands the
    filtered result here to render only the current page (the ~184-voice list was
    unusable rendered all at once — the 04-06 checkpoint defect). Returns
    ``(page_items, total, page, n_pages)`` where:

      - ``total``      is ``len(items)`` (the full filtered count, for the caption).
      - ``n_pages``    is ``ceil(total / page_size)``, at least 1 (an empty list is one
                       empty page, so the page control always has a valid 1..n range).
      - ``page``       is the input page CLAMPED into ``1..n_pages`` — a page beyond the
                       end (e.g. after a filter shrank the result) clamps to the last
                       page, and ``0``/negative clamps to ``1``. The clamped value is
                       returned so the caller can write it back to the page control.
      - ``page_items`` is the ``page_size``-long slice for the clamped page (the final
                       page may be shorter).

    Pure: no streamlit, no I/O — mirrors the Phase-3 ``resolve_selected_voice_id``
    precedent so the slicing/clamping is unit-testable without a ScriptRunContext. A
    non-positive ``page_size`` is treated as 1 (defensive — never a zero-division).
    """
    size = max(1, int(page_size))
    seq = list(items)
    total = len(seq)
    n_pages = max(1, (total + size - 1) // size)
    page = max(1, min(int(page), n_pages))
    start = (page - 1) * size
    return seq[start:start + size], total, page, n_pages


def _filter_hash(*parts) -> str:
    """A stable string fingerprint of the cross-engine filter/page-size selection.

    The browser keeps the current page in ``st.session_state``; whenever the filter
    tuple (engine / language / quality / search) OR the page size changes, the page
    must reset to 1 (a filter change re-filters the WHOLE dataset, so a remembered
    page-3 is meaningless against the new, possibly-shorter result). Hashing the
    selection into one token lets the caller detect any change with a single equality
    check. Pure / Streamlit-free so the reset logic is unit-testable.
    """
    return "␟".join("" if p is None else str(p) for p in parts)


def _voice_table_row(engine: str, voice) -> dict:
    """One read-only table row for the cross-engine ``st.dataframe`` (D-10).

    Maps an (engine, override-applied voice) pair to the column dict the table shows:
    Engine, Voice ID, Name, Language, Tier, Gender, Tags (the custom tags joined for
    display). Pure / Streamlit-free so the column shape is unit-testable. The merged
    voice is passed in so the displayed attributes/tags already reflect the user's
    overrides.
    """
    return {
        "Engine": engine,
        "Voice ID": voice.id,
        "Name": voice.name,
        "Language": voice.language or "",
        "Tier": voice.tier or "",
        "Gender": voice.gender or "",
        "Tags": ", ".join(voice.tags),
    }


def _voice_select_label(engine: str, voice) -> str:
    """The select-to-edit option label for one voice: ``engine · name (id)`` (D-10/D-15).

    Used by the "Select a voice to edit labels" picker below the read-only table so the
    user can pick any voice in the current FILTERED set and open the existing label
    editor for it. Pure / Streamlit-free.
    """
    return f"{engine} · {voice.name} ({voice.id})"


def _render_label_editor(engine: str, base_voice, merged_voice) -> None:
    """Per-voice label/tag editor (D-14/D-15), inside an expander on a browser row.

    Pre-fills from the CURRENTLY MERGED voice (so an existing override is shown), lets
    the user override display name / language / quality tier / gender and edit a
    comma-separated custom-tags list, and on Save writes the JSON-valued app_settings
    key via ``set_label_overrides`` — only when something actually changed (mirrors the
    write-only-on-change durable-pref idiom). Works for ANY engine's voice because it
    operates on the ``(engine, voice.id)`` pair from the cross-engine browser (D-15).
    After a save it clears the shared voice cache and reruns so the new attributes
    immediately drive the filters/search here AND refresh the other pickers (no restart).
    A "Reset to defaults" action removes the override entirely. The original engine
    label is shown as a caption so the user can see what they are overriding.
    """
    existing = get_label_overrides(config.storage.database_path, engine, base_voice.id)
    with st.expander("Edit labels & tags"):
        st.caption(
            f"Original: **{base_voice.name}** · {base_voice.language} · "
            f"{base_voice.tier} · {base_voice.gender}"
        )
        _kid = f"{engine}:{base_voice.id}"
        new_name = st.text_input(
            "Display name", value=merged_voice.name, key=f"lbl_name_{_kid}"
        )
        c1, c2 = st.columns(2)
        with c1:
            new_lang = st.text_input(
                "Language", value=merged_voice.language,
                key=f"lbl_lang_{_kid}",
                help="e.g. en-us, fr-fr — drives the Language filter.",
            )
            new_tier = st.text_input(
                "Quality tier", value=merged_voice.tier, key=f"lbl_tier_{_kid}",
                help="e.g. enhanced, standard, compact — drives the Quality filter.",
            )
        with c2:
            new_gender = st.text_input(
                "Gender", value=merged_voice.gender, key=f"lbl_gender_{_kid}"
            )
            new_tags_raw = st.text_input(
                "Custom tags (comma-separated)",
                value=", ".join(merged_voice.tags),
                key=f"lbl_tags_{_kid}",
                help="Free-text tags — searchable in the box above (e.g. audiobook, calm).",
            )

        _save_col, _reset_col = st.columns(2)
        with _save_col:
            if st.button("Save labels", key=f"lbl_save_{_kid}", type="primary"):
                overrides: dict = {}
                # Persist a field override only when it differs from the engine's
                # ORIGINAL value — so clearing a field back to the original removes it.
                if new_name.strip() and new_name.strip() != base_voice.name:
                    overrides["name"] = new_name.strip()
                if new_lang.strip() and new_lang.strip().lower() != (base_voice.language or "").lower():
                    overrides["language"] = new_lang.strip().lower()
                if new_tier.strip() and new_tier.strip().lower() != (base_voice.tier or "").lower():
                    overrides["tier"] = new_tier.strip().lower()
                if new_gender.strip() and new_gender.strip().lower() != (base_voice.gender or "").lower():
                    overrides["gender"] = new_gender.strip()
                tags = _parse_tags(new_tags_raw)
                if tags:
                    overrides["tags"] = tags
                if overrides != existing:
                    set_label_overrides(
                        config.storage.database_path, engine, base_voice.id, overrides
                    )
                    clear_voice_cache()  # new labels feed the filters without a restart
                    st.success("Labels saved.")
                    st.rerun()
                else:
                    st.caption("No changes to save.")
        with _reset_col:
            if existing and st.button("Reset to defaults", key=f"lbl_reset_{_kid}"):
                set_label_overrides(
                    config.storage.database_path, engine, base_voice.id, {}
                )
                clear_voice_cache()
                st.success("Reset to the engine's original labels.")
                st.rerun()


def _engine_default_voice(engine_name: str, config_default: str) -> str:
    """Cheap per-engine default voice id without loading heavy engine models.

    native_os exposes its OS-default via a no-model NativeOSEngine; kokoro/piper load
    models in create_engine, so they must not be instantiated per rerun just to read
    a default — fall back to the saved config voice for those.
    """
    if engine_name == "native_os":
        from diana.tts.native_os_engine import NativeOSEngine
        eng = NativeOSEngine()
        getter = getattr(eng, "default_voice", lambda: "")
        return getter()
    return config_default or ""


# Platform-neutral OS-voice-download hint (D-10; Pitfall 3 — no hardcoded breadcrumb).
_NATIVE_HINT = (
    "Want higher-quality or more voices? Your operating system can download extra "
    "voices for free — no terminal needed. On macOS, open **System Settings** and "
    "search for *Spoken Content* or *System Voices*. On Windows, open **Settings ▸ "
    "Time & Language ▸ Speech** and add voices. New voices appear here after download."
)


def _sync_streamlit_config(max_upload_mb: int, theme: str = "device") -> None:
    """Update .streamlit/config.toml with current settings."""
    config_dir = Path(".streamlit")
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "config.toml"

    base = detect_device_theme() if theme == "device" else theme

    config_path.write_text(
        "[client]\n"
        'toolbarMode = "minimal"\n'
        "\n"
        "[browser]\n"
        "gatherUsageStats = false\n"
        "\n"
        "[server]\n"
        "headless = true\n"
        f"maxUploadSize = {max_upload_mb}\n"
        "\n"
        "[theme]\n"
        'font = "serif"\n'
        f'base = "{base}"\n'
    )

st.set_page_config(
    page_title="Diana's Settings",
    page_icon=get_icon_image(),
    layout="wide",
)

config = get_config()
setup_sidebar()

st.markdown("## *Settings*")

# D-09: Settings is the management hub, restructured into tabs with a dedicated
# Voices tab. st.tabs renders ALL bodies each run (not lazy) — the cached
# _cached_voices keeps that cheap (RESEARCH lines 516-525).
tab_general, tab_voices, tab_processing, tab_llm, tab_news = st.tabs(
    ["General", "Voices", "Processing", "LLM Cleaning", "News"]
)

# ---------------------------------------------------------------------------
# General — TTS engine / default voice / paths / dashboard / speed
# ---------------------------------------------------------------------------
with tab_general:
    st.subheader("TTS Engine")

    _engines = list_engines()
    _saved_engine = config.tts.engine
    if _saved_engine not in _engines:
        logger.warning("Saved TTS engine %r no longer available; falling back to kokoro", _saved_engine)
        _saved_engine = "kokoro"
    engine = st.selectbox(
        "Default Engine",
        _engines,
        index=_engines.index(_saved_engine),
    )

    # Voice dropdown populated dynamically from the selected engine, with the same
    # language/quality filters + name search + per-engine default treatment as Upload.
    _all_voices = _cached_voices(engine)

    _langs = sorted({(v.language or "").strip().lower() for v in _all_voices if v.language})
    _sys_lang = (config.tts.language or "").strip().lower()
    if _sys_lang in _langs:
        _langs = [_sys_lang] + [l for l in _langs if l != _sys_lang]
    _lang_choice = st.selectbox(
        "Language", ["All languages"] + _langs, index=0, key=f"settings_lang_{engine}"
    )
    _sel_language = None if _lang_choice == "All languages" else _lang_choice

    _tiers = sorted({(v.tier or "").strip().lower() for v in _all_voices if v.tier})
    _tier_choice = st.selectbox(
        "Quality", ["All qualities"] + _tiers, index=0, key=f"settings_tier_{engine}"
    )
    _sel_tier = None if _tier_choice == "All qualities" else _tier_choice

    _name_query = st.text_input(
        "Search voices", value="", placeholder="Type part of a name…",
        key=f"settings_voicesearch_{engine}",
    )

    _filtered = filter_voices(
        _all_voices, language=_sel_language, tier=_sel_tier, query=_name_query or None
    )
    voices = _system_language_first(_filtered, config.tts.language)
    voice_options = {v.name: v.id for v in voices}
    voice_display = list(voice_options.keys())

    # Per-engine default voice, validated against the live list (D-03, Pitfall 5).
    _engine_default = _engine_default_voice(engine, config.tts.voice)
    _resolved_default = resolve_default_voice(
        config.storage.database_path, engine, _all_voices, _engine_default
    )
    default_voice_idx = 0
    for i, v in enumerate(voices):
        if v.id == _resolved_default:
            default_voice_idx = i
            break
    if voice_display:
        selected_voice_name = st.selectbox(
            "Default Voice", voice_display, index=default_voice_idx, key=f"settings_voice_{engine}"
        )
    else:
        # Filters/search matched no voice: an empty selectbox returns None. Show a
        # friendly nudge and fall back to the empty id (= use the engine/OS default).
        st.info(
            "No voices match your filters. Clear the language/quality filter or "
            "search box to see all voices."
        )
        selected_voice_name = None
    selected_voice_id = resolve_selected_voice_id(voice_options, selected_voice_name)

    # Persist the per-engine choice durably (write only on change) — mirrors Upload so
    # the two pages agree on the remembered voice (D-03). Empty id = "use OS default",
    # which we don't snapshot.
    _pref_key = f"tts.default_voice.{engine}"
    if selected_voice_id and selected_voice_id != get_setting(
        config.storage.database_path, _pref_key, None
    ):
        set_setting(config.storage.database_path, _pref_key, selected_voice_id)

    # Dismissible OS-voice-download hint for native_os (D-10), durable dismissed flag
    # shared with the Upload page.
    if engine == "native_os":
        _hint_dismissed = (
            get_setting(config.storage.database_path, "tts.native_hint_dismissed", "0") == "1"
        )
        if not _hint_dismissed:
            _hint_col, _btn_col = st.columns([6, 1])
            with _hint_col:
                st.info(_NATIVE_HINT)
            with _btn_col:
                if st.button("Dismiss", key="settings_dismiss_native_hint"):
                    set_setting(config.storage.database_path, "tts.native_hint_dismissed", "1")
                    st.rerun()

    speed = st.slider(
        "Default Speed",
        min_value=0.5, max_value=2.0, value=config.tts.speed, step=0.1,
    )

    st.subheader("Dashboard")

    theme_options = ["device", "light", "dark"]
    theme = st.selectbox(
        "Theme",
        theme_options,
        index=theme_options.index(config.dashboard.theme),
    )

    max_upload_mb = st.number_input(
        "Max upload size (MB)",
        min_value=1, max_value=10240,
        value=config.dashboard.max_upload_mb, step=100,
    )

    st.subheader("Kokoro Model Paths")
    kokoro_model = st.text_input(
        "Model file", value=config.tts.kokoro.model_path
    )
    kokoro_voices = st.text_input(
        "Voices file", value=config.tts.kokoro.voices_path
    )

    st.subheader("Piper Model Path")
    piper_model = st.text_input(
        "Piper model file", value=config.tts.piper.model_path
    )

# ---------------------------------------------------------------------------
# Voices — the management hub (D-09). Full catalog browse (curated-flat default +
# Show-all grouped-by-language over the refreshable manifest, D-01/D-02/D-03),
# three-mode preview (bundled/fetched sample + live synth, D-12/VOICE-03), and
# validated dual-path manual import (upload + path, D-13/VOICE-04/HARD-03). The
# install machinery itself (badge -> disk-check -> threaded resumable download ->
# md5 atomic install -> selectable) is the Plan-03 walking slice, reused per row.
# ---------------------------------------------------------------------------
with tab_voices:
    st.subheader("Voices")

    # -----------------------------------------------------------------------
    # Cross-engine browser + per-voice label editor (D-10/D-14/D-15). Lists
    # EVERY engine's voices together (native_os + Kokoro + Piper) with their
    # custom overrides merged in, an engine filter alongside the reused Phase-3
    # language/quality filters + name/tag search, and a per-voice editor that
    # overrides name/language/tier/gender and adds free-text tags — for ANY
    # engine's voice (D-15). Custom labels/tags immediately drive the filters.
    # -----------------------------------------------------------------------
    st.markdown("#### Browse all voices")
    st.caption(
        "Every engine's voices in one place. Filter by engine, language or quality, "
        "search by name or your own tags, and edit any voice's labels — the changes "
        "drive the filters everywhere and persist across restarts."
    )

    # Cached cross-engine enumeration (cleared on install/import/label-save).
    _engine_pairs = cached_all_engine_voices()

    # Merge each voice's stored overrides BEFORE filtering/display so a relabeled
    # language/tier filters correctly and a custom tag is searchable (D-14). Keep the
    # un-merged base alongside the merged voice for the editor (change detection).
    _db_path = config.storage.database_path
    _merged_rows = [
        (
            _eng,
            _v,
            apply_overrides(_v, get_label_overrides(_db_path, _eng, _v.id)),
        )
        for _eng, _v in _engine_pairs
    ]

    # Engine filter (D-10) alongside the reused Phase-3 language/quality + search.
    _xe_engine_col, _xe_lang_col, _xe_tier_col = st.columns(3)
    with _xe_engine_col:
        _engine_opts = ["All engines"] + list_engines()
        _xe_engine = st.selectbox("Engine", _engine_opts, index=0, key="xe_engine")
    with _xe_lang_col:
        _xe_langs = sorted({
            (m.language or "").strip().lower() for _, _, m in _merged_rows if m.language
        })
        _xe_lang_choice = st.selectbox(
            "Language", ["All languages"] + _xe_langs, index=0, key="xe_lang"
        )
        _xe_sel_language = None if _xe_lang_choice == "All languages" else _xe_lang_choice
    with _xe_tier_col:
        _xe_tiers = sorted({
            (m.tier or "").strip().lower() for _, _, m in _merged_rows if m.tier
        })
        _xe_tier_choice = st.selectbox(
            "Quality", ["All qualities"] + _xe_tiers, index=0, key="xe_tier"
        )
        _xe_sel_tier = None if _xe_tier_choice == "All qualities" else _xe_tier_choice

    _xe_query = st.text_input(
        "Search voices (name or tag)", value="", placeholder="Type part of a name or tag…",
        key="xe_search",
    )

    # Apply the engine filter first, then the reused Phase-3 filter_voices over the
    # MERGED voices (so overridden language/tier/name match). The search box ORs a
    # name match (filter_voices query) with a plain-substring tag match (search_by_tag)
    # — both accent-folded, never a compiled user regex (T-04-REDOS).
    _xe_rows = [
        (e, b, m) for (e, b, m) in _merged_rows
        if (_xe_engine == "All engines" or e == _xe_engine)
    ]
    _merged_only = [m for _, _, m in _xe_rows]
    _name_hits = filter_voices(
        _merged_only, language=_xe_sel_language, tier=_xe_sel_tier,
        query=_xe_query or None,
    )
    _name_hit_ids = {id(v) for v in _name_hits}
    if _xe_query.strip():
        # Also surface voices whose CUSTOM TAGS match the query (name search alone
        # would miss a tag-only hit). Tag matches still respect the engine/lang/tier
        # filters applied above.
        _tag_prefiltered = filter_voices(
            _merged_only, language=_xe_sel_language, tier=_xe_sel_tier,
        )
        _tag_hits = search_by_tag(_tag_prefiltered, _xe_query)
        _name_hit_ids |= {id(v) for v in _tag_hits}
    _visible = [(e, b, m) for (e, b, m) in _xe_rows if id(m) in _name_hit_ids]
    # Order best-quality-first within the visible set (D-09), stable.
    _visible_ordered = order_by_quality([m for _, _, m in _visible])
    _ordered_ids = [id(m) for m in _visible_ordered]
    _visible.sort(key=lambda row: _ordered_ids.index(id(row[2])))

    if not _visible:
        st.info(
            "No voices match your filters. Clear the engine/language/quality filter "
            "or the search box to see every voice."
        )
    else:
        # PAGINATED READ-ONLY TABLE (04-06 checkpoint fix). The ~184 cross-engine voices
        # were unusable rendered all at once; now the FULL filtered set above is sliced
        # into one page here. The page-size selector + page number live in session_state;
        # any filter OR page-size change resets to page 1 (a remembered page is
        # meaningless against a freshly-filtered, possibly-shorter result). The filter
        # work is ALL done above (over the full dataset) — only the final slice happens
        # here, so the engine/language/quality/search controls always filter everything,
        # never just the visible page (the load-bearing requirement).
        _size_col, _page_col = st.columns([1, 2])
        with _size_col:
            _page_size = st.selectbox(
                "Per page", [25, 50, 100], index=0, key="xeng_page_size",
                help="How many voices to show per page.",
            )

        # Reset to page 1 whenever the filter selection OR the page size changes. The
        # fingerprint folds every filter control + the page size into one token; when it
        # differs from the last render we drop the remembered page back to 1 BEFORE the
        # page-number widget is created so the widget shows 1 (D-09 None-safe discipline).
        _sel_hash = _filter_hash(
            _xe_engine, _xe_sel_language, _xe_sel_tier, _xe_query, _page_size
        )
        if st.session_state.get("_xeng_filter_hash") != _sel_hash:
            st.session_state["_xeng_filter_hash"] = _sel_hash
            st.session_state["xeng_page"] = 1

        # Clamp the remembered page into the valid range and WRITE IT BACK before the
        # page-number widget is created, so the widget's own state is already valid and
        # we never pass an out-of-range `value=` (which Streamlit warns about when a key
        # already lives in session_state). paginate() owns the clamp (stale page beyond a
        # now-shorter result snaps to the last page) so the table never shows empty.
        _page_items, _total, _page, _n_pages = paginate(
            _visible, st.session_state.get("xeng_page", 1), _page_size
        )
        st.session_state["xeng_page"] = _page

        with _page_col:
            if _n_pages > 1:
                # No `value=`: the widget reads the clamped page from session_state by
                # key, so navigating updates it and the slice below re-reads it.
                _page = int(st.number_input(
                    "Page", min_value=1, max_value=_n_pages, step=1,
                    key="xeng_page",
                    help=f"{_n_pages} pages of voices.",
                ))
                # Re-slice from the (possibly) newly-picked page so the table below
                # reflects this run's page without waiting for the next rerun.
                _page_items, _total, _page, _n_pages = paginate(
                    _visible, _page, _page_size
                )
            else:
                st.caption("Page 1 of 1")

        # The "Showing X–Y of N voices" caption over the read-only table.
        _start = (_page - 1) * _page_size + 1
        _end = _start + len(_page_items) - 1
        st.caption(f"Showing {_start}–{_end} of {_total} voices")

        # Read-only table of THIS page (built-in st.dataframe — no new dependency).
        # Columns: Engine, Voice ID, Name, Language, Tier, Gender, Tags. Editing happens
        # in the select-to-edit panel below, not in the table (it is display-only).
        _table_rows = [_voice_table_row(_eng, _m) for _eng, _b, _m in _page_items]
        st.dataframe(_table_rows, width="stretch", hide_index=True)

        # SELECT-TO-EDIT (D-14/D-15): pick ANY voice in the current FILTERED set (not
        # just the visible page) and open the existing per-voice label/tag editor for it.
        # Options span the whole filtered result so a voice on another page is still
        # editable without first navigating to its page.
        st.markdown("##### Edit a voice's labels")
        _edit_options = {
            _voice_select_label(_eng, _m): (_eng, _b, _m)
            for _eng, _b, _m in _visible
        }
        _edit_choice = st.selectbox(
            "Select a voice to edit labels",
            ["—"] + list(_edit_options.keys()),
            index=0,
            key="xeng_edit_select",
            help="Pick any voice from the filtered list above to rename it, change its "
                 "language/tier/gender, or add custom tags.",
        )
        if _edit_choice != "—":
            _sel_eng, _sel_base, _sel_merged = _edit_options[_edit_choice]
            _cross_engine_badge(_sel_eng, _sel_merged)
            _render_label_editor(_sel_eng, _sel_base, _sel_merged)

    # -----------------------------------------------------------------------
    # Engine models (D-19): the engine-level Kokoro model download. native_os is
    # OS-owned (nothing to download/uninstall) and Piper is per-voice below, so this
    # block is just the single Kokoro model row — the same generic download substrate
    # as Piper, proving the layer is engine-generic before Phase 5 reuses it.
    # -----------------------------------------------------------------------
    st.divider()
    st.markdown("#### Engine models")
    st.caption(
        "Kokoro is one model with many built-in voices — download it once here to "
        "use them. native_os voices are provided by your operating system (nothing "
        "to download or uninstall)."
    )
    _render_kokoro_download_row()

    # -----------------------------------------------------------------------
    # Heavy opt-in engines (Phase 5, HEAVY-01): higher-quality neural engines that
    # are NOT bundled — the user installs them on demand here (deps + model weights in
    # one action, no terminal). Each row reuses the generic heavy-engine install row
    # (footprint confirm + disk pre-check + two-phase progress + uninstall). Orpheus is
    # the first; F5/Fish join in their own waves. The default install stays untouched
    # (D-02): nothing here is downloaded or imported until the user clicks Install.
    # -----------------------------------------------------------------------
    st.divider()
    st.markdown("#### Heavy opt-in engines")
    st.caption(
        "Higher-quality neural voices that run entirely on your machine. They are not "
        "included by default — install one on demand below (a one-time download, no "
        "terminal needed). You can uninstall to reclaim the space at any time."
    )
    _render_heavy_engine_row("orpheus", orpheus_install_spec())

    # -----------------------------------------------------------------------
    # Bulk partial-download cleanup (D-18): clear ALL orphaned ``.part`` files left by
    # interrupted downloads in the per-user model cache in one click. Per-item "Remove
    # partial" lives on each Piper catalog row below; this clears every orphan at once.
    # -----------------------------------------------------------------------
    st.divider()
    st.markdown("#### Clean up partial downloads")
    st.caption(
        "Interrupted downloads leave temporary `.part` files in your model cache. "
        "Remove them all at once if you no longer want to resume them."
    )
    if st.button("Clean up partial downloads"):
        _removed = clean_partials(paths.model_dir())
        if _removed:
            st.success(
                f"Removed {_removed} partial download file{'s' if _removed != 1 else ''}."
            )
        else:
            st.info("No partial downloads to clean up.")

    st.divider()
    st.markdown("#### Install Piper voices")
    st.caption(
        "Browse and install Piper voices on demand — no terminal needed. Voices "
        "download into your per-user cache and become selectable for a job. Preview "
        "any voice before installing, or import a voice you already have on disk."
    )

    # Per-row speed for the installed-voice live preview (same scale as Upload).
    _preview_speed = config.tts.speed

    # BROWSE controls: Show-all toggle + Refresh + the reused Phase-3 filters (D-03).
    _ctl_show, _ctl_refresh = st.columns([3, 1])
    with _ctl_show:
        _show_all = st.toggle(
            "Show all voices",
            value=False,
            help="Off: a curated best-per-language list (offline). On: the full "
                 "catalog grouped by language. Use Refresh catalog to fetch the latest.",
        )
    with _ctl_refresh:
        if st.button("Refresh catalog", help="Re-fetch the live voice list (D-02)."):
            with st.spinner("Refreshing catalog…"):
                _refresh_catalog_state()
            st.rerun()

    _browse_voices = _catalog_voices(_show_all)
    _raw_entries = _catalog_raw_entries()

    # Reused Phase-3 filter/search widgets, pointed at CATALOG data — language options
    # derive from the manifest, not OS voices (D-03). Plain substring search (no regex).
    _langs = sorted({(v.language or "").strip().lower() for v in _browse_voices if v.language})
    _lang_choice = st.selectbox(
        "Language", ["All languages"] + _langs, index=0, key="catalog_lang"
    )
    _sel_language = None if _lang_choice == "All languages" else _lang_choice

    _tiers = sorted({(v.tier or "").strip().lower() for v in _browse_voices if v.tier})
    _tier_choice = st.selectbox(
        "Quality", ["All qualities"] + _tiers, index=0, key="catalog_tier"
    )
    _sel_tier = None if _tier_choice == "All qualities" else _tier_choice

    _name_query = st.text_input(
        "Search voices", value="", placeholder="Type part of a name…",
        key="catalog_search",
    )

    _filtered = order_by_quality(
        filter_voices(
            _browse_voices, language=_sel_language, tier=_sel_tier,
            query=_name_query or None,
        )
    )

    if not _filtered:
        # Empty filter/search result must not crash (Phase-3 None-safe discipline).
        st.info(
            "No voices match your filters. Clear the language/quality filter or "
            "search box to see the catalog."
        )
    elif _show_all:
        # Show-all: grouped by language in collapsible sections (D-03) — a flat
        # ~900-row list would be unusable.
        _grouped = catalog.group_by_language(_filtered)
        for _lang in sorted(_grouped):
            _bucket = _grouped[_lang]
            with st.expander(f"{_lang or 'unknown'} ({len(_bucket)})"):
                for _v in _bucket:
                    _render_voice_row(_v, _raw_entries.get(_v.id, {}), _preview_speed)
    else:
        # Curated default: a flat list (offline, instant) — D-01.
        for _v in _filtered:
            _render_voice_row(_v, _raw_entries.get(_v.id, {}), _preview_speed)

    st.caption(
        "Tip: after a voice finishes installing it appears in the **Default Voice** "
        "picker (General tab) and the Upload page when you pick the Piper engine."
    )

    # IMPORT (D-13/VOICE-04): BOTH in-app upload AND a path on disk, each validated
    # through safe_voice_dest (extension allow-list + traversal containment, HARD-03).
    st.divider()
    st.subheader("Import a voice")
    st.caption(
        "Already have a Piper voice? Import its `.onnx` model and the matching "
        "`.onnx.json` config. Both files are required."
    )

    _up_files = st.file_uploader(
        "Upload the .onnx + .onnx.json pair",
        type=["onnx", "json"],
        accept_multiple_files=True,
        help="Select BOTH files. If the .onnx is larger than the upload size limit "
             "(Settings ▸ General ▸ Max upload size), use the path option below.",
        key="voice_import_uploader",
    )
    if st.button("Import uploaded files", key="import_uploaded"):
        _ok, _msg = _import_voice_pair(_up_files)
        if _ok:
            clear_voice_cache()  # make the new voice appear in pickers without restart
            st.success(_msg)
        else:
            st.error(_msg)

    st.markdown("**Or import from a path on disk** (sidesteps the upload size limit):")
    _path_str = st.text_input(
        "Full path to the .onnx file",
        placeholder="/path/to/en_US-amy-medium.onnx",
        key="voice_import_path",
        label_visibility="collapsed",
    )
    if st.button("Import from path", key="import_from_path"):
        _ok, _msg = _import_voice_from_path(_path_str)
        if _ok:
            clear_voice_cache()
            st.success(_msg)
        else:
            st.error(_msg)

# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------
with tab_processing:
    st.subheader("Processing")

    chunk_max = st.number_input(
        "Max characters per chunk",
        min_value=500, max_value=10000,
        value=config.processing.chunk_max_chars, step=500,
    )
    bitrate = st.selectbox(
        "Output bitrate",
        ["128k", "192k", "256k", "320k"],
        index=["128k", "192k", "256k", "320k"].index(
            config.processing.output_bitrate
        ),
    )
    gap_ms = st.number_input(
        "Silence between chunks (ms)",
        min_value=0, max_value=3000,
        value=config.processing.gap_ms, step=100,
    )

# ---------------------------------------------------------------------------
# LLM Text Cleaning (optional)
# ---------------------------------------------------------------------------
with tab_llm:
    st.subheader("LLM Text Cleaning (Optional)")
    # Reserve a slot for the active/inactive status — populated after the widgets
    # below so it can reflect live form state on each rerun.
    _llm_status_slot = st.empty()
    st.info(
        "For security, enter your API key as an environment variable reference like "
        "`${OPENAI_API_KEY}` and set the actual key in your shell. "
        "The placeholder is saved to config.yaml, not the real key."
    )

    llm_enabled = st.toggle("Enable LLM cleaning", value=config.llm.enabled)
    _llm_provider_options = ["openai", "anthropic", "anthropic-cli", "google"]
    _current_provider = config.llm.provider if config.llm.provider in _llm_provider_options else "openai"
    llm_provider = st.selectbox(
        "Provider",
        _llm_provider_options,
        index=_llm_provider_options.index(_current_provider),
        disabled=not llm_enabled,
    )
    if llm_provider == "anthropic-cli":
        st.info(
            "Anthropic CLI uses your Claude Code login. Run `claude login` in a "
            "terminal first — no API key needed. Uses your Pro/Max subscription."
        )
        llm_api_key = ""
    else:
        llm_api_key = st.text_input(
            "API Key",
            value=config.llm.api_key,
            type="password",
            placeholder="${OPENAI_API_KEY}",
            disabled=not llm_enabled,
        )
    llm_model = st.text_input(
        "Model override (leave blank for default)",
        value=config.llm.model,
        placeholder="gpt-4o-mini",
        disabled=not llm_enabled,
    )
    llm_language = st.text_input(
        "Translate to language (leave blank to skip)",
        value=config.llm.target_language,
        placeholder="e.g. English, Spanish",
        disabled=not llm_enabled,
    )
    llm_max_concurrent = st.number_input(
        "Max concurrent LLM calls",
        min_value=1, max_value=16,
        value=config.llm.max_concurrent_calls, step=1,
        help="Number of text chunks processed in parallel. Higher values are faster but may hit API rate limits.",
        disabled=not llm_enabled,
    )

    _ENV_RE = __import__("re").compile(r"^\$\{[A-Z_][A-Z0-9_]*\}$")
    if llm_enabled and llm_provider != "anthropic-cli" and llm_api_key and not _ENV_RE.match(llm_api_key.strip()):
        st.warning(
            "The API key will be stored in plaintext in config.yaml. "
            "Use `${YOUR_ENV_VAR}` to store a reference instead."
        )

    # Populate the top-of-section status slot. Mirrors diana.llm.registry.get_llm_config
    # so Settings agrees with what Upload/News see.
    _key_typed = (llm_api_key or "").strip()
    _key_unresolved = _key_typed.startswith("${")
    with _llm_status_slot.container():
        if not llm_enabled:
            st.caption("LLM cleaning is disabled — text cleaning runs on-device (rule-based).")
        elif llm_provider == "anthropic-cli":
            st.success(
                "Active: anthropic-cli (uses your local Claude Code login; no API key required)."
            )
        elif not _key_typed:
            st.warning(
                "Not active: no API key set — cleaning falls back to rule-based (on-device). "
                "Nothing leaves your machine."
            )
        elif _key_unresolved:
            st.warning(
                f"Not active: API key reference `{llm_api_key}` is unresolved (env var not set) "
                "— cleaning falls back to rule-based (on-device). Nothing leaves your machine."
            )
        else:
            st.success(f"Active: {llm_provider} with API key configured.")

# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------
with tab_news:
    st.subheader("News")
    news_max_stories = st.number_input(
        "Max stories per category",
        min_value=1,
        max_value=20,
        value=config.news.max_stories_per_category,
        step=1,
        help="Maximum stories the AI will return per category each time you fetch.",
    )

# ---------------------------------------------------------------------------
# Save — single button persists every tab's settings (lives in General-side flow
# but rendered outside the tabs so it is always reachable).
# ---------------------------------------------------------------------------
st.divider()

if st.button("Save Settings", type="primary"):
    # Validate model paths for the selected engine. native_os is OS-provided —
    # it has NO model file, so it skips path validation entirely (D-02/NATIVE-04).
    warnings = []
    if engine == "native_os":
        pass  # OS-provided voices: no model file to validate
    elif engine == "kokoro":
        if not Path(kokoro_model).exists():
            warnings.append(f"Kokoro model file not found: {kokoro_model}")
        if not Path(kokoro_voices).exists():
            warnings.append(f"Kokoro voices file not found: {kokoro_voices}")
    elif engine == "piper":
        if not Path(piper_model).exists():
            warnings.append(f"Piper model file not found: {piper_model}")

    config.tts.engine = engine
    config.tts.voice = selected_voice_id
    config.tts.speed = speed
    config.processing.chunk_max_chars = chunk_max
    config.processing.output_bitrate = bitrate
    config.processing.gap_ms = gap_ms
    config.dashboard.max_upload_mb = max_upload_mb
    config.dashboard.theme = theme
    config.tts.kokoro.model_path = kokoro_model
    config.tts.kokoro.voices_path = kokoro_voices
    config.tts.piper.model_path = piper_model
    config.llm.enabled = llm_enabled
    config.llm.provider = llm_provider
    config.llm.api_key = llm_api_key
    config.llm.model = llm_model
    config.llm.target_language = llm_language
    config.llm.max_concurrent_calls = int(llm_max_concurrent)
    config.news.max_stories_per_category = int(news_max_stories)
    save_config(config)
    _sync_streamlit_config(max_upload_mb, theme)

    for w in warnings:
        st.warning(w)
    if warnings:
        st.success("Settings saved, but model files above are missing. TTS may fail until they are provided.")
    else:
        st.success("Settings saved. Restart the app for theme and upload size changes to take effect.")
