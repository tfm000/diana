import asyncio
import os
import uuid
from pathlib import Path

import streamlit as st

from diana.config import get_config
from diana.dashboard.sidebar import get_icon_image, setup_sidebar
from diana.database import create_job, init_db
from diana.models import Job, JobStatus, parse_page_range
from diana.tts.registry import create_engine, get_engine_voices, list_engines

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
    "Choose a PDF, EPUB, or TXT file",
    type=["pdf", "epub", "txt"],
    accept_multiple_files=False,
)

st.subheader("TTS Settings")

col1, col2, col3 = st.columns(3)

with col1:
    engine_name = st.selectbox("Engine", list_engines(), index=list_engines().index(config.tts.engine))

with col2:
    voices = get_engine_voices(engine_name, config=config)
    voice_options = {v.name: v.id for v in voices}
    voice_display = list(voice_options.keys())
    default_idx = 0
    for i, v in enumerate(voices):
        if v.id == config.tts.voice:
            default_idx = i
            break
    selected_voice_name = st.selectbox(
        "Voice", voice_display, index=default_idx, key=f"voice_{engine_name}"
    )
    selected_voice_id = voice_options[selected_voice_name] if voice_options else ""

with col3:
    speed = st.slider("Speed", min_value=0.5, max_value=2.0, value=config.tts.speed, step=0.1)

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

_API_ENGINES = {"openai_tts", "elevenlabs"}
_audio_fmt = "audio/mp3" if engine_name in _API_ENGINES else "audio/wav"

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

    if st.button(
        "Convert to Audio",
        type="primary",
        disabled=st.session_state.get("job_submitted", False),
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
        )
        create_job(config.storage.database_path, job)

        # Clean up temp file if it still exists
        tmp_path.unlink(missing_ok=True)

        st.success(f"Job created for **{safe_name}**. Head to the Library to track progress.")
        st.page_link("pages/2_Library.py", label="Go to Library", icon="\U0001f4da")
