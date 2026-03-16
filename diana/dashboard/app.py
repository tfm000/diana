import logging
from pathlib import Path

import streamlit as st

from diana.config import get_config
from diana.database import init_db
from diana.processing import worker as _worker_module
from diana.processing.worker import JobWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

config = get_config()

st.set_page_config(
    page_title=config.dashboard.page_title,
    page_icon="\U0001f3a7",
    layout="wide",
)

# Ensure data directories exist
for d in (config.storage.upload_dir, config.storage.chunk_dir,
          config.storage.output_dir, config.storage.model_dir):
    Path(d).mkdir(parents=True, exist_ok=True)

# Initialize database
init_db(config.storage.database_path)

# Start background worker once per server process
if not getattr(_worker_module, "_started", False):
    _worker_module._started = True
    _worker = JobWorker(config)
    _worker.start()

st.title("Diana")
st.markdown("Convert documents to speech. Upload a file to get started.")
st.page_link("pages/1_Upload.py", label="Upload a Document", icon="\U0001f4c4")
st.page_link("pages/2_Library.py", label="View Library", icon="\U0001f4da")
st.page_link("pages/3_Settings.py", label="Settings", icon="\u2699\ufe0f")
