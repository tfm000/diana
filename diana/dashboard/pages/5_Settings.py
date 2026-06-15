import asyncio
import json
import logging
import threading
from importlib import resources
from pathlib import Path

import streamlit as st

from diana import paths
from diana.config import get_config, save_config
from diana.dashboard.sidebar import get_icon_image, setup_sidebar
from diana.dashboard.voice_cache import cached_voices as _cached_voices
from diana.dashboard.voice_cache import clear_voice_cache
from diana.database import get_setting, set_setting
from diana.downloads.downloader import download_file, has_space
from diana.tts import catalog, install_state
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
    else:
        total = state["total"] or 1
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
