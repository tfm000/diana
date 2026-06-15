import json
import logging
import threading
from importlib import resources
from pathlib import Path

import streamlit as st

from diana import paths
from diana.config import get_config, save_config
from diana.dashboard.sidebar import get_icon_image, setup_sidebar
from diana.database import get_setting, set_setting
from diana.downloads.downloader import download_file, has_space
from diana.tts import catalog, install_state
from diana.tts.native_os_engine import (
    filter_voices,
    order_by_quality,
    resolve_selected_voice_id,
)
from diana.tts.registry import (
    get_engine_voices,
    list_engines,
    resolve_default_voice,
)
from diana.utils import detect_device_theme

logger = logging.getLogger(__name__)


@st.cache_data(show_spinner=False)
def _cached_voices(engine_name: str):
    """Enumerate an engine's voices once per engine, cached across reruns (D-04).

    st.tabs renders ALL tab bodies on every run (they are not lazy), so the Voices
    tab and the General tab both pull voices on each rerun — caching keeps tab
    switching from re-shelling ``say`` (T-03-12 / RESEARCH lines 516-525).
    """
    return get_engine_voices(engine_name, config=get_config())


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
    ``.part`` for Resume (D-06/D-07). Any exception lands in ``state["error"]``.
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
                return  # D-07: stop here, .part kept for Resume (D-06)
            completed_bytes += (size or 0)
            state["downloaded"] = completed_bytes
        state["done"] = True
    except Exception as e:  # noqa: BLE001 — surface to the UI, NEVER st.* on this thread
        state["error"] = str(e)


def _new_dl_state(total: int) -> dict:
    """A fresh per-voice download-state record for ``st.session_state.dl_state``."""
    return {"downloaded": 0, "total": total, "done": False, "error": None, "cancel": False}


@st.fragment(run_every="0.5s")
def _render_download_progress(voice_id: str) -> None:
    """Poll ``dl_state[voice_id]`` from the SCRIPT thread and draw progress (D-08).

    Runs as an ``st.fragment`` so it refreshes itself every 0.5s WITHOUT a full-page
    rerun — the page stays responsive while bytes stream (ENGINE-04). Every ``st.*``
    here executes on the script thread (safe); the download thread only mutates the
    shared dict this reads. Once ``done``/``error`` is set, the auto-refresh stops
    re-arming work because the next click rebuilds state.
    """
    dl_state = st.session_state.get("dl_state", {})
    state = dl_state.get(voice_id)
    if not state:
        return
    if state["error"]:
        st.error(f"Download failed: {state['error']}")
    elif state["done"]:
        st.success("Installed.")
    else:
        total = state["total"] or 1
        st.progress(
            min(state["downloaded"] / total, 1.0),
            text=f"{state['downloaded'] / 1e6:.1f} / {total / 1e6:.1f} MB",
        )


def _start_piper_download(voice_id: str, entry: dict, footprint: int) -> None:
    """Spawn the download thread for ``voice_id`` unless one is already in-flight.

    Pitfall 3 / T-04-RETRIG: a Streamlit rerun (or a double-click) must NOT spawn a
    second writer thread for the same voice — that would corrupt the shared ``.part``.
    Guard on the live ``dl_state`` record: only spawn when none exists or the prior
    attempt finished (done/error). One in-flight download is serialized per voice id
    (RESEARCH Open Question 3).
    """
    if "dl_state" not in st.session_state:
        st.session_state.dl_state = {}
    existing = st.session_state.dl_state.get(voice_id)
    if existing and not existing["done"] and not existing["error"]:
        return  # already downloading — do not double-spawn (Pitfall 3)
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
# Voices — the management hub (D-09). This plan ships the WALKING SLICE: install
# ONE curated Piper voice end-to-end (badge -> disk-check -> threaded resumable
# download -> md5 atomic install -> selectable). Full browse/filter/preview/import/
# uninstall/Kokoro reuse land in Plans 04-06.
# ---------------------------------------------------------------------------
with tab_voices:
    st.subheader("Voices")
    st.caption(
        "Install additional Piper voices on demand — no terminal needed. Voices "
        "download into your per-user cache and become selectable for a job. "
        "Full catalog browse, preview, import, and uninstall arrive soon."
    )

    _curated_entries = _curated_piper_entries()
    _curated_voices = catalog.curated_subset(catalog.load_bundled_manifest())

    for _v in _curated_voices:
        _entry = _curated_entries.get(_v.id, {})
        _installed = install_state.piper_voice_installed(_v.id)
        # Footprint: on-disk size when installed, else the manifest estimate (D-11).
        _footprint = (
            install_state.piper_footprint_bytes(_v.id)
            if _installed
            else catalog.voice_footprint_bytes(_entry)
        )
        _mb = _footprint / 1e6

        with st.container(border=True):
            _info_col, _action_col = st.columns([3, 1])
            with _info_col:
                st.markdown(f"**{_v.name}**  \n`{_v.id}` · {_v.language} · {_v.tier}")
                # ENGINE-03 / D-11 install-state + footprint badge.
                if _installed:
                    st.success(f"Ready · {_mb:.1f} MB on disk", icon="✅")
                else:
                    st.caption(f"~{_mb:.1f} MB, downloads on first use")

            _dl_state = st.session_state.get("dl_state", {})
            _state = _dl_state.get(_v.id)
            _in_flight = bool(_state) and not _state["done"] and not _state["error"]
            _interrupted = bool(_state) and not _state["done"] and bool(_state["error"])

            with _action_col:
                if _installed and not _in_flight:
                    st.button("Installed", key=f"installed_{_v.id}", disabled=True)
                elif _in_flight:
                    # D-07: Cancel halts but keeps the .part for a later Resume.
                    if st.button("Cancel", key=f"cancel_{_v.id}"):
                        _state["cancel"] = True
                elif _interrupted:
                    # D-06: Resume re-spawns the download, which offsets from the
                    # existing .part rather than restarting from zero.
                    if st.button("Resume", key=f"resume_{_v.id}"):
                        _start_piper_download(_v.id, _entry, int(_footprint))
                        st.rerun()
                else:
                    if st.button("Install", key=f"install_{_v.id}", type="primary"):
                        # D-05: universal disk-space pre-check gates EVERY download.
                        # Refuse before a byte is written when space is insufficient.
                        _ok, _free = has_space(paths.model_dir(), int(_footprint))
                        if not _ok:
                            st.error(
                                f"Not enough disk space: need ~{_footprint / 1e6:.1f} MB "
                                f"(plus headroom), only {_free / 1e6:.1f} MB free. "
                                "Free up space and try again."
                            )
                        else:
                            _start_piper_download(_v.id, _entry, int(_footprint))
                            st.rerun()

            # Live byte-progress / result, polled from the script thread (D-08).
            if _state and (_in_flight or _state["done"] or _state["error"]):
                _render_download_progress(_v.id)

    st.divider()
    st.caption(
        "Tip: after a voice finishes installing it appears in the **Default Voice** "
        "picker (General tab) and the Upload page when you pick the Piper engine."
    )

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
