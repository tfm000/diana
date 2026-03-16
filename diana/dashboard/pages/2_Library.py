import time
from pathlib import Path

import streamlit as st

from diana.config import get_config
from diana.database import delete_job, init_db, list_jobs
from diana.models import JobStatus

config = get_config()
init_db(config.storage.database_path)

st.header("Library")

jobs = list_jobs(config.storage.database_path, limit=100)

if not jobs:
    st.info("No jobs yet. Upload a document to get started.")
    st.page_link("pages/1_Upload.py", label="Upload a Document", icon="\U0001f4c4")
else:
    for job in jobs:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

            with col1:
                st.markdown(f"**{job.filename}**")
                st.caption(f"Engine: {job.tts_engine} | Voice: {job.tts_voice}")

            with col2:
                status = job.status
                if status == JobStatus.COMPLETED:
                    st.success("Completed")
                elif status == JobStatus.FAILED:
                    st.error("Failed")
                    if job.error_message:
                        st.caption(job.error_message[:200])
                elif status == JobStatus.SYNTHESIZING:
                    st.info(f"Synthesizing... ({job.completed_chunks}/{job.total_chunks})")
                    if job.total_chunks > 0:
                        st.progress(job.progress)
                elif status == JobStatus.PENDING:
                    st.warning("Pending")
                else:
                    st.info(status.value.capitalize())

            with col3:
                if status == JobStatus.COMPLETED and job.output_path:
                    output_path = Path(job.output_path)
                    if output_path.exists():
                        st.audio(str(output_path), format="audio/mp3")
                        with open(output_path, "rb") as f:
                            st.download_button(
                                "Download MP3",
                                data=f.read(),
                                file_name=f"{Path(job.filename).stem}.mp3",
                                mime="audio/mpeg",
                                key=f"dl_{job.id}",
                            )

            with col4:
                if st.button("Delete", key=f"del_{job.id}", type="secondary"):
                    delete_job(config.storage.database_path, job.id)
                    st.rerun()

    # Auto-refresh if any jobs are still processing
    active_statuses = {JobStatus.PENDING, JobStatus.EXTRACTING, JobStatus.CHUNKING,
                       JobStatus.SYNTHESIZING, JobStatus.MERGING}
    if any(j.status in active_statuses for j in jobs):
        time.sleep(3)
        st.rerun()
