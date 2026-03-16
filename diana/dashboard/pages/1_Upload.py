import uuid
from pathlib import Path

import streamlit as st

from diana.config import get_config
from diana.database import create_job, init_db
from diana.models import Job, JobStatus
from diana.tts.registry import create_engine, list_engines

config = get_config()
init_db(config.storage.database_path)

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
    # Load voices for selected engine
    try:
        # Build a temporary engine config to get voices
        temp_config = get_config()
        temp_config.tts.engine = engine_name
        engine = create_engine(temp_config)
        voices = engine.list_voices()
        engine.shutdown()
        voice_options = {v.name: v.id for v in voices}
        voice_display = list(voice_options.keys())
        # Find default selection
        default_idx = 0
        for i, v in enumerate(voices):
            if v.id == config.tts.voice:
                default_idx = i
                break
        selected_voice_name = st.selectbox("Voice", voice_display, index=default_idx)
        selected_voice_id = voice_options[selected_voice_name]
    except Exception as e:
        st.warning(f"Could not load voices for {engine_name}: {e}")
        selected_voice_id = st.text_input("Voice ID", value=config.tts.voice)

with col3:
    speed = st.slider("Speed", min_value=0.5, max_value=2.0, value=config.tts.speed, step=0.1)

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
