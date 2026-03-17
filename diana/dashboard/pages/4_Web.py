import asyncio
import uuid
from urllib.parse import urlparse

import streamlit as st

from diana.config import get_config
from diana.dashboard.sidebar import get_icon_image, setup_sidebar
from diana.database import create_job, init_db
from diana.llm.registry import get_llm_config
from diana.models import Job, JobStatus
from diana.news.scraper import ScraperError, scrape_source
from diana.tts.registry import get_engine_voices, list_engines

st.set_page_config(
    page_title="Diana's Web",
    page_icon=get_icon_image(),
    layout="wide",
)

config = get_config()
db_path = config.storage.database_path
init_db(db_path)
setup_sidebar()

st.markdown("## *Web URL to Audio*")
st.write("Paste any webpage URL and Diana will scrape it, clean the text, and convert it to an MP3.")

# ---------------------------------------------------------------------------
# URL input
# ---------------------------------------------------------------------------
url_input = st.text_input(
    "Webpage URL",
    placeholder="https://www.example.com/article",
)


def _valid_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# LLM toggle (only shown if LLM is configured)
# ---------------------------------------------------------------------------
llm_cfg = get_llm_config(config)
use_llm = False
if llm_cfg is not None:
    use_llm = st.toggle(
        "Clean with LLM",
        value=True,
        help="Use the configured LLM to clean scraped text before TTS. "
             "Falls back to rule-based cleaning if disabled.",
    )

# ---------------------------------------------------------------------------
# TTS settings
# ---------------------------------------------------------------------------
st.subheader("TTS Settings")
col1, col2, col3 = st.columns(3)

with col1:
    engine_name = st.selectbox(
        "Engine", list_engines(),
        index=list_engines().index(config.tts.engine),
    )

with col2:
    voices = get_engine_voices(engine_name, config=config)
    voice_opts = {v.name: v.id for v in voices}
    voice_display = list(voice_opts.keys())
    default_idx = 0
    for i, v in enumerate(voices):
        if v.id == config.tts.voice:
            default_idx = i
            break
    selected_voice_name = st.selectbox(
        "Voice", voice_display, index=default_idx, key=f"web_voice_{engine_name}"
    )
    selected_voice_id = voice_opts.get(selected_voice_name, "")

with col3:
    speed = st.slider("Speed", 0.5, 2.0, config.tts.speed, 0.1, key="web_speed")

# ---------------------------------------------------------------------------
# Fetch & Convert
# ---------------------------------------------------------------------------
if st.button("Fetch & Convert", type="primary"):
    url = url_input.strip()
    if not url:
        st.error("Please enter a URL.")
    elif not _valid_url(url):
        st.error("Please enter a valid http/https URL.")
    elif not selected_voice_id:
        st.error("No voice available for this engine. Check your API key in Settings.")
    else:
        with st.spinner(f"Fetching {url}…"):
            try:
                _, scraped_text = scrape_source(url)
            except ScraperError as exc:
                st.error(f"Failed to fetch the page: {exc}")
                st.stop()

        if not scraped_text.strip():
            st.error("No readable text found at that URL.")
            st.stop()

        # The pipeline will handle cleaning (LLM or rule-based) based on config.
        # For the web job type, the URL is stored as upload_path; the pipeline
        # scrapes it again at processing time so the text is always fresh.
        import os
        from pathlib import Path

        # Store scraped text as a temp file so pipeline can reference it;
        # also store job as file_type="web" so pipeline re-scrapes via URL.
        job_id = str(uuid.uuid4())
        hostname = urlparse(url).netloc.replace("www.", "")
        filename = f"{hostname}.web"

        job = Job(
            id=job_id,
            filename=filename,
            file_type="web",
            upload_path=url,          # pipeline uses URL to re-scrape
            status=JobStatus.PENDING,
            tts_engine=engine_name,
            tts_voice=selected_voice_id,
        )

        # Ensure upload dir exists
        Path(config.storage.upload_dir).mkdir(parents=True, exist_ok=True)
        create_job(db_path, job)

        st.success(f"Job created for **{filename}**. Head to the Library to track progress.")
        st.page_link("pages/2_Library.py", label="Go to Library", icon="📚")

        if not use_llm and llm_cfg is not None:
            st.info("LLM cleaning is disabled for this job. Rule-based cleaning will be used.")
