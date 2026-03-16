import asyncio
import uuid
from pathlib import Path

import streamlit as st

from diana.config import get_config
from diana.dashboard.sidebar import get_icon_image, setup_sidebar
from diana.database import create_job, init_db
from diana.models import Job, JobStatus
from diana.tts.registry import create_engine, get_engine_voices, list_engines

st.set_page_config(
    page_title="Diana's Upload",
    page_icon=get_icon_image(),
    layout="wide",
)

config = get_config()
init_db(config.storage.database_path)
setup_sidebar()

st.header("Upload a Document")

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
    voices = get_engine_voices(engine_name)
    voice_options = {v.name: v.id for v in voices}
    voice_display = list(voice_options.keys())
    default_idx = 0
    for i, v in enumerate(voices):
        if v.id == config.tts.voice:
            default_idx = i
            break
    selected_voice_name = st.selectbox("Voice", voice_display, index=default_idx)
    selected_voice_id = voice_options[selected_voice_name]

with col3:
    speed = st.slider("Speed", min_value=0.5, max_value=2.0, value=config.tts.speed, step=0.1)

# Voice preview
PREVIEW_TEXT = "Hello, this is a preview of my voice. Welcome to Diana."

if st.button("Preview Voice"):
    cache_key = f"preview_{engine_name}_{selected_voice_id}"
    if cache_key in st.session_state:
        st.audio(st.session_state[cache_key], format="audio/wav")
    else:
        try:
            with st.spinner("Generating voice preview..."):
                engine = create_engine(config)
                audio_bytes = asyncio.run(
                    engine.synthesize(PREVIEW_TEXT, voice=selected_voice_id, speed=speed)
                )
                engine.shutdown()
                st.session_state[cache_key] = audio_bytes
                st.audio(audio_bytes, format="audio/wav")
        except Exception as e:
            st.error(f"Preview failed: {e}")
elif any(k.startswith(f"preview_{engine_name}_{selected_voice_id}") for k in st.session_state):
    cache_key = f"preview_{engine_name}_{selected_voice_id}"
    if cache_key in st.session_state:
        st.audio(st.session_state[cache_key], format="audio/wav")

st.divider()

if uploaded_file is not None:
    if st.button("Convert to Audio", type="primary"):
        job_id = str(uuid.uuid4())
        ext = Path(uploaded_file.name).suffix.lower()

        # Save uploaded file
        upload_dir = Path(config.storage.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        upload_path = upload_dir / f"{job_id}_{uploaded_file.name}"
        upload_path.write_bytes(uploaded_file.getvalue())

        # Create job
        job = Job(
            id=job_id,
            filename=uploaded_file.name,
            file_type=ext.lstrip("."),
            upload_path=str(upload_path),
            status=JobStatus.PENDING,
            tts_engine=engine_name,
            tts_voice=selected_voice_id,
        )
        create_job(config.storage.database_path, job)

        st.success(f"Job created for **{uploaded_file.name}**. Head to the Library to track progress.")
        st.page_link("pages/2_Library.py", label="Go to Library", icon="\U0001f4da")
