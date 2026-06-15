import asyncio
import logging
import os
import uuid
from pathlib import Path

import streamlit as st

from diana.config import get_config
from diana.dashboard.sidebar import get_icon_image, setup_sidebar
from diana.dashboard.voice_cache import cached_voices as _cached_voices
from diana.database import create_job, get_setting, init_db, set_setting
from diana.llm.registry import get_llm_config
from diana.models import Job, JobStatus, parse_page_range
from diana.tts import install_state
from diana.tts.native_os_engine import (
    filter_voices,
    order_by_quality,
    resolve_selected_voice_id,
)
from diana.tts.registry import (
    create_engine,
    heavy_engine_failfast,
    list_engines,
    resolve_default_voice,
    resolve_engine_name,
)

logger = logging.getLogger(__name__)


def _system_language_first(voices, system_lang):
    """Order voices best-quality-first (D-09), system-language voices ahead (D-08).

    Sorts the system language's voices before all others, then applies the pure
    quality ordering within each group (stable, so the quality order is preserved).
    """
    sys_lang = (system_lang or "").strip().lower()
    in_lang = [v for v in voices if (v.language or "").strip().lower() == sys_lang]
    others = [v for v in voices if (v.language or "").strip().lower() != sys_lang]
    return order_by_quality(in_lang) + order_by_quality(others)


def _engine_readiness(engine_name: str) -> tuple[bool, str]:
    """Cheap (no heavy import) readiness + footprint note for an engine (ENGINE-03/D-11).

    Returns ``(ready, note)`` for the badge below the Upload engine dropdown:
      - native_os: always ready — OS-provided voices, nothing to download (NATIVE-04).
      - piper: ready if ANY Piper voice is already installed on disk; otherwise a
        "~X MB, downloads on first use" estimate from the curated catalog's smallest
        voice (so the number reflects a real first install, not a guess).
      - kokoro: ready if the model + voices bin are present, else its ~download note.

    Detection is the ``install_state`` filesystem probe ONLY — no onnxruntime/piper/
    kokoro import on this render path (ENGINE-01 / threat T-04-NOIMPORT).
    """
    if engine_name == "native_os":
        return True, "Ready — uses your operating system's built-in voices (no download)."
    if engine_name == "piper":
        if install_state.list_installed_piper_voice_ids():
            return True, "Ready — at least one Piper voice is installed."
        # Smallest curated voice ~ the minimum first-use download (cheap, offline).
        try:
            from diana.tts import catalog
            sizes = [
                catalog.voice_footprint_bytes(e)
                for e in catalog._load_bundled_raw().values()
            ]
            sizes = [s for s in sizes if s]
            est = min(sizes) / 1e6 if sizes else 0
        except Exception:  # noqa: BLE001 — a missing catalog never breaks the badge
            est = 0
        note = (
            f"~{est:.0f} MB+, downloads on first use — install voices in Settings ▸ Voices."
            if est else
            "Downloads on first use — install voices in Settings ▸ Voices."
        )
        return False, note
    if engine_name == "kokoro":
        if install_state.kokoro_model_installed():
            return True, "Ready — the Kokoro model is installed."
        return False, "~80 MB+, the Kokoro model downloads on first use."
    if engine_name == "orpheus":
        # Heavy opt-in engine (HEAVY-01): a pure filesystem probe of the per-engine
        # venv + marker (NO orpheus_cpp/llama_cpp import here — ENGINE-01 / D-17).
        if install_state.heavy_engine_installed("orpheus"):
            return True, "Ready — Orpheus is installed."
        return False, "~2.3 GB+, install Orpheus in Settings ▸ Voices."
    return False, ""


def _engine_default_voice(engine_name: str, config_default: str) -> str:
    """Cheap per-engine default voice id, without loading heavy engine models.

    native_os exposes its OS-default via a no-model NativeOSEngine instance (empty
    id => OS system default, D-02). Other engines (kokoro/piper) load ONNX/voice
    models in create_engine, so we must NOT instantiate them just to read a default
    on every rerun — fall back to the saved config voice for those.
    """
    if engine_name == "native_os":
        from diana.tts.native_os_engine import NativeOSEngine
        eng = NativeOSEngine()                       # __init__ loads nothing
        getter = getattr(eng, "default_voice", lambda: "")
        return getter()
    return config_default or ""


# Generic D-10 hint — wording stays platform-neutral (Pitfall 3: macOS 15 Sequoia
# moved the voice-download UI, so a hardcoded breadcrumb would mislead).
_NATIVE_HINT = (
    "Want higher-quality or more voices? Your operating system can download extra "
    "voices for free — no terminal needed. On macOS, open **System Settings** and "
    "search for *Spoken Content* or *System Voices*. On Windows, open **Settings ▸ "
    "Time & Language ▸ Speech** and add voices. New voices appear here after download."
)

st.set_page_config(
    page_title="Diana's Upload",
    page_icon=get_icon_image(),
    layout="wide",
)

config = get_config()
init_db(config.storage.database_path)
setup_sidebar()

st.markdown("## *Upload a Document*")

uploaded_file = st.file_uploader(
    "Choose a PDF, EPUB, TXT, or MD file",
    type=["pdf", "epub", "txt", "md"],
    accept_multiple_files=False,
)

st.subheader("TTS Settings")

col1, col2, col3 = st.columns(3)

with col1:
    engines = list_engines()
    saved = config.tts.engine
    if saved not in engines:
        logger.warning("Saved TTS engine %r no longer available; falling back to kokoro", saved)
        saved = resolve_engine_name(saved)
    engine_name = st.selectbox("Engine", engines, index=engines.index(saved))

    # ENGINE-03 / D-11: install-state + footprint readiness badge below the engine
    # select (st.selectbox can't render rich per-option badges). Cheap detection via
    # the install_state filesystem probe — NO heavy SDK import here (ENGINE-01).
    _ready, _ready_note = _engine_readiness(engine_name)
    if _ready:
        st.success(_ready_note, icon="✅")
    else:
        st.caption(_ready_note)

with col2:
    all_voices = _cached_voices(engine_name)

    # Language + quality filters and a name search around the voice picker (D-07).
    _langs = sorted({(v.language or "").strip().lower() for v in all_voices if v.language})
    # System language first in the filter options (D-08).
    _sys_lang = (config.tts.language or "").strip().lower()
    if _sys_lang in _langs:
        _langs = [_sys_lang] + [l for l in _langs if l != _sys_lang]
    lang_options = ["All languages"] + _langs
    lang_choice = st.selectbox("Language", lang_options, index=0, key=f"lang_{engine_name}")
    sel_language = None if lang_choice == "All languages" else lang_choice

    _tiers = sorted({(v.tier or "").strip().lower() for v in all_voices if v.tier})
    tier_options = ["All qualities"] + _tiers
    tier_choice = st.selectbox("Quality", tier_options, index=0, key=f"tier_{engine_name}")
    sel_tier = None if tier_choice == "All qualities" else tier_choice

    name_query = st.text_input(
        "Search voices", value="", placeholder="Type part of a name…",
        key=f"voicesearch_{engine_name}",
    )

    # Filter -> order best-quality-first, system-language voices ahead (D-07/08/09).
    filtered = filter_voices(
        all_voices, language=sel_language, tier=sel_tier, query=name_query or None
    )
    voices = _system_language_first(filtered, config.tts.language)

    voice_options = {v.name: v.id for v in voices}
    voice_display = list(voice_options.keys())

    # Per-engine default voice from durable prefs, validated against the live list so
    # a stale/cross-engine id is never preselected (D-03, Pitfall 5). Falls back to the
    # engine's own default (native_os = OS system default, empty id).
    _engine_default = _engine_default_voice(engine_name, config.tts.voice)
    _resolved_default = resolve_default_voice(
        config.storage.database_path, engine_name, all_voices, _engine_default
    )
    default_idx = 0
    for i, v in enumerate(voices):
        if v.id == _resolved_default:
            default_idx = i
            break

    if voice_display:
        selected_voice_name = st.selectbox(
            "Voice", voice_display, index=default_idx, key=f"voice_{engine_name}"
        )
    else:
        # Filters/search matched no voice: an empty selectbox returns None and
        # indexing the options would crash. Show a friendly, non-technical nudge
        # and fall back to the empty id (= use the engine/OS default voice).
        st.info(
            "No voices match your filters. Clear the language/quality filter or "
            "search box to see all voices."
        )
        selected_voice_name = None
    selected_voice_id = resolve_selected_voice_id(voice_options, selected_voice_name)

    # Remember the per-engine choice durably (write only on change) — survives
    # restart and engine switching (D-03). Don't persist an empty id (= "use OS
    # default"), so the OS default stays dynamic rather than snapshotted.
    _pref_key = f"tts.default_voice.{engine_name}"
    if selected_voice_id and selected_voice_id != get_setting(
        config.storage.database_path, _pref_key, None
    ):
        set_setting(config.storage.database_path, _pref_key, selected_voice_id)

with col3:
    speed = st.slider("Speed", min_value=0.5, max_value=2.0, value=config.tts.speed, step=0.1)

# Dismissible hint pointing to the OS's own voice downloads (D-10), shown only for
# native_os. The dismissed flag is durable (app_settings) so it stays dismissed
# across restart. Wording is platform-neutral (Pitfall 3).
if engine_name == "native_os":
    _hint_dismissed = (
        get_setting(config.storage.database_path, "tts.native_hint_dismissed", "0") == "1"
    )
    if not _hint_dismissed:
        _hint_col, _btn_col = st.columns([6, 1])
        with _hint_col:
            st.info(_NATIVE_HINT)
        with _btn_col:
            if st.button("Dismiss", key="dismiss_native_hint"):
                set_setting(config.storage.database_path, "tts.native_hint_dismissed", "1")
                st.rerun()

# Per-job LLM cleaning toggle — privacy-first (default OFF), provider-gated, and durable
# across restarts via the app_settings store (key "upload.use_llm"). The Upload page
# remembers its own choice independently of other pages (D-06/D-07/D-08/D-10).
llm_available = get_llm_config(config) is not None
remembered = get_setting(config.storage.database_path, "upload.use_llm", "0") == "1"
use_llm = st.toggle(
    "Clean with AI (LLM)",
    value=remembered and llm_available,
    disabled=not llm_available,
    help=(
        "Sends the document text to your configured LLM provider to clean it before "
        "narration. Off = on-device rule-based cleaning, so nothing leaves your machine."
        if llm_available
        else "Disabled — configure an LLM provider in Settings to enable AI cleaning."
    ),
)
if llm_available and use_llm != remembered:
    set_setting(config.storage.database_path, "upload.use_llm", "1" if use_llm else "0")

# Reset job_submitted when engine or voice changes so user can re-submit the same file
_curr_combo = f"{engine_name}:{selected_voice_id}"
if st.session_state.get("_last_engine_voice") != _curr_combo:
    st.session_state["_last_engine_voice"] = _curr_combo
    st.session_state["job_submitted"] = False

# Voice preview
DEFAULT_PREVIEW_TEXT = "Hello, this is a preview of my voice. Welcome to Diana."
preview_text = st.text_area(
    "Preview text",
    value=DEFAULT_PREVIEW_TEXT,
    height=68,
    help="Type custom text to hear how the selected voice sounds.",
)

# kokoro and piper both output WAV (the only remaining engines)
_audio_fmt = "audio/wav"

if st.button("Preview Voice"):
    if not preview_text.strip():
        st.warning("Enter some text to preview.")
    elif not selected_voice_id:
        st.warning("No voices available for this engine. Check your API key in Settings.")
    else:
        cache_key = f"preview_{engine_name}_{selected_voice_id}_{hash(preview_text)}"
        if cache_key in st.session_state:
            st.audio(st.session_state[cache_key], format=_audio_fmt)
        else:
            try:
                with st.spinner("Generating voice preview..."):
                    engine = create_engine(config, engine_name=engine_name)
                    audio_bytes = asyncio.run(
                        engine.synthesize(preview_text, voice=selected_voice_id, speed=speed)
                    )
                    engine.shutdown()
                    st.session_state[cache_key] = audio_bytes
                    st.audio(audio_bytes, format=_audio_fmt)
            except Exception as e:
                st.error(f"Preview failed: {e}")
else:
    # Show cached preview if available
    cache_key = f"preview_{engine_name}_{selected_voice_id}_{hash(preview_text)}"
    if cache_key in st.session_state:
        st.audio(st.session_state[cache_key], format=_audio_fmt)

st.divider()

# Reset submission state when a new file is uploaded
if "last_uploaded_name" not in st.session_state:
    st.session_state.last_uploaded_name = None

if uploaded_file is not None:
    safe_name = os.path.basename(uploaded_file.name)
    ext = Path(safe_name).suffix.lower()

    # Reset submit flag on new file
    if st.session_state.last_uploaded_name != safe_name:
        st.session_state.last_uploaded_name = safe_name
        st.session_state.job_submitted = False

    # Save to a temp path so we can inspect page/chapter count
    tmp_dir = Path(config.storage.upload_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"_preview_{safe_name}"

    # Verify resolved path is within upload dir
    if not str(tmp_path.resolve()).startswith(str(tmp_dir.resolve())):
        st.error("Invalid filename.")
        st.stop()

    tmp_path.write_bytes(uploaded_file.getvalue())

    # Show page/chapter selection for multi-page formats
    page_range_spec = ""
    total = 0
    if ext == ".pdf":
        from diana.parsers.pdf_parser import PDFParser
        total = PDFParser.page_count(str(tmp_path))
        st.info(f"This PDF has **{total}** page{'s' if total != 1 else ''}.")
        page_range_spec = st.text_input(
            "Page range (leave empty for all pages)",
            placeholder="e.g. 1-3, 5, 10-15",
            help="Specify pages using ranges and/or individual numbers, separated by commas. Pages are 1-based.",
        )
    elif ext == ".epub":
        from diana.parsers.epub_parser import EPUBParser
        total = EPUBParser.chapter_count(str(tmp_path))
        st.info(f"This EPUB has **{total}** chapter{'s' if total != 1 else ''} (sections with text).")
        page_range_spec = st.text_input(
            "Chapter range (leave empty for all chapters)",
            placeholder="e.g. 1-3, 5, 10-15",
            help="Specify chapters using ranges and/or individual numbers, separated by commas. Chapters are 1-based.",
        )

    # Validate page range input
    if page_range_spec.strip() and total > 0:
        try:
            parsed = parse_page_range(page_range_spec, total)
            if parsed:
                display = ", ".join(str(p + 1) for p in parsed[:20])
                if len(parsed) > 20:
                    display += "..."
                st.success(f"Will convert {len(parsed)} of {total}: {display}")
            else:
                st.warning("No valid pages matched. All pages will be converted.")
        except ValueError as e:
            st.error(f"Invalid page range: {e}")

    # D-16 fail-fast: a heavy engine chosen before it is installed disables Convert
    # with an actionable "install it in Settings ▸ Voices" prompt, so the job NEVER
    # starts and never errors mid-conversion. This generic gate (heavy_engine_failfast
    # -> _HEAVY_ENGINES) already covers orpheus/f5/fish; non-heavy engines are never
    # gated. Cheap probe only — NO heavy SDK import (ENGINE-01).
    _failfast = heavy_engine_failfast(engine_name)
    if _failfast:
        st.error(_failfast)

    if st.button(
        "Convert to Audio",
        type="primary",
        disabled=st.session_state.get("job_submitted", False) or bool(_failfast),
    ):
        st.session_state.job_submitted = True
        job_id = str(uuid.uuid4())

        # Move temp file to its permanent name
        upload_path = tmp_dir / f"{job_id}_{safe_name}"
        tmp_path.rename(upload_path)

        # Create job
        job = Job(
            id=job_id,
            filename=safe_name,
            file_type=ext.lstrip("."),
            upload_path=str(upload_path),
            status=JobStatus.PENDING,
            tts_engine=engine_name,
            tts_voice=selected_voice_id,
            page_range=page_range_spec if page_range_spec.strip() else None,
            use_llm=use_llm,
        )
        create_job(config.storage.database_path, job)

        # Clean up temp file if it still exists
        tmp_path.unlink(missing_ok=True)

        st.success(f"Job created for **{safe_name}**. Head to the Library to track progress.")
        st.page_link("pages/2_Library.py", label="Go to Library", icon="\U0001f4da")
